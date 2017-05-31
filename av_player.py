#! /usr/bin/env python

import weakref
import argparse
import functools
import pathlib
import ctypes
import struct, array
import os
import sys
import pprint
import time
import collections
from qtproxy import Q

import av
import mpv
from av_propertymodel import *
class AVFlatPropertyModel(Q.QAbstractTableModel):

    Mimetype = 'application/vnd.row.list'

    def __init__(self, player,parent=None):
        super().__init__(parent)
        self._player = player
        self._all_properties = list(sorted(self._player.m.properties|self._player.m.options))
        self._props = [[_,] for _ in sorted(self._all_properties)]
        [self.data(self.createIndex(_,1)) for _ in range(len(self._props))]

    def data(self, index, role=Q.Qt.DisplayRole):
        if not index.isValid() or index.row() > len(self._props):
            return None
        if role == Q.Qt.DisplayRole or role == Q.Qt.EditRole:
            row = index.row()
            if index.column() == 0:
                return self._props[row][0]
            elif index.column() == 1:
                if len(self._props[row]) < 2:
                    prop = self._player.get_property( self._props[row][0])
                    if not isinstance(prop,AVProperty):
                        prop=None
                    self._props[row].append(prop)
                    if prop:
                        prop.valueChanged.connect(lambda:self.dataChanged.emit(index,index))
                else:
                    prop = self._props[row][1]
                if prop:
                    try:
                        return prop.value()
                    except:
                        pass
        return None
    def flags(self, index):
        if index.isValid() and index.column() == 1:
            return Q.Qt.ItemIsEditable|Q.Qt.ItemIsEnabled|Q.Qt.ItemIsSelectable
        elif index.isValid():
            return Q.Qt.ItemIsEnabled|Q.Qt.ItemIsSelectable
        else:
            return 0

    def setData(self, index, value, role=Q.Qt.DisplayRole):
        if not index.isValid() or index.row() > len(self._props):
            return False
        if role == Q.Qt.DisplayRole or role == Q.Qt.EditRole:
            row = index.row()
            if index.column() != 1:
                return False
            if len(self._props[row]) < 2:
                prop = self._player.get_property(self._props[row][0])
                if not isinstance(prop,AVProperty):
                    prop=None
                self._props[row].append(prop)
                if prop:
                    prop.valueChanged.connect(lambda:self.dataChanged.emit(index,index))
            else:
                prop = self._props[row][1]
            if prop:
                try:
                    prop.setValue(value)
                    return True
                except:
                    pass
        return False

    def rowCount(self,parent=Q.QModelIndex()):
        return len(self._props)
    def columnCount(self,parent=Q.QModelIndex()):
        return 2

class AVProperty(Q.QObject):
    mpv = __import__('mpv')
    valueChanged = Q.pyqtSignal(object)
    _value = None

    @property
    def propertyName(self):
        return self.objectName()

    @property
    def context(self):
        return self.__context__

    @Q.pyqtSlot()
    def value(self):
        return self._value
#        return getattr(self.context,self.objectName())

    @Q.pyqtSlot(object)
    def setValue(self, value):
        if self._value != value:
            self._value = value
            setattr(self.context,self.objectName(),value)

    def _emitValueChanged(self, value):
        if self._value != value:
            self._value = value
            self.valueChanged.emit(value)

#    def __bool__(self):
#        return bool(self.value())
    def __int__(self):
        return int(self.value())
    def __float__(self):
        return float(self.value())
    def __index__(self):
        return int(self)
    def __str__(self):
        return str(self.value())
    def __bytes__(self):
        return bytes(self.value())
    def __init__(self, prop, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__context__  = ctx
        prop = ctx.attr_name(prop)
        self.setObjectName(prop)
#        ctx.request_event(ctx.mpv.EventType.property_change,True)
        try:self._value = self.context.get_property(self.objectName())
        except:self._value = None
        reply_userdata = lambda val:self._emitValueChanged(val)
        ctx_ref = weakref.ref(ctx)
        def unobserve_cb(val):
            ctx = ctx_ref()
            try:ctx.unobserve_property(val)
            except:pass
        self.reply_userdata = reply_userdata
        ctx.observe_property(prop,reply_userdata)
        self._finalizer = weakref.finalize(self,unobserve_cb, reply_userdata)

class AVPlayer(Q.QOpenGLWidget):
    pfl = Q.QOpenGLVersionProfile()
    pfl.setVersion(4,1)
    pfl.setProfile(Q.QSurfaceFormat.CoreProfile)

    base_options = {
         'input-default-bindings':True
        ,'input_vo_keyboard':True
        ,'gapless_audio':True
        ,'osc':True
        ,'keep-open':False
        ,'load_scripts':False
        ,'ytdl':True
        ,'force-window':True
        ,'vo':'opengl-cb'
        ,'hr-seek':True
        ,'hwdec-preload':True
        ,'hwdec':'vdpau'
        ,'opengl-hwdec-interop':'vdpau-glx'
#        , 'player-operation-mode':'pseudo-gui'
          }

    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
#    playlistChanged = Q.pyqtSignal(object)
#    playlist_posChanged = Q.pyqtSignal(int)
#    time_posChanged = Q.pyqtSignal(object)
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
#    speedChanged = Q.pyqtSignal(object)
#    durationChanged = Q.pyqtSignal(object)
#    video_paramsChanged = Q.pyqtSignal(object)
    wakeup = Q.pyqtSignal()
    mpv_event = Q.pyqtSignal()
    logMessage = Q.pyqtSignal(object)
    just_die = Q.pyqtSignal()
    mpv = __import__('mpv')

    def get_property(self, prop):
        try: prop_name = self.m.attr_name(prop)
        except: return
        if not prop_name: return
        binding = self.findChild(AVProperty, prop_name)
        if binding:
            return binding
#            raise AttributeError
#                prop_name = prop
#                pass
        prop_object = AVProperty(prop_name, ctx=self.m,parent=self)
        setattr(self,prop,      prop_object)
        if not hasattr(self,prop_name):
            setattr(self,prop_name, prop_object)
        return prop_object

    def __getattr__(self, prop):
        try: prop_name = self.m.attr_name(prop)
        except:
            raise AttributeError
        if not prop_name:
            raise AttributeError
        binding = self.findChild(AVProperty, prop_name)
        if binding:
            return binding
        prop_object = AVProperty(prop_name, ctx=self.m,parent=self)
        setattr(self,prop,      prop_object)
        if not hasattr(self,prop_name):
            setattr(self,prop_name, prop_object)
        return prop_object

        return self.get_property(prop)

    @staticmethod
    def get_options(*args,**kwargs):
        options = kwargs
        media   = list()
        for arg in args:
            if arg.startswith('--'):
                arg,_,value = arg[2:].partition('=')
                options[arg]=value or True
                continue
            media.append(arg)
        return options,media

    def __init__(self, *args,fp=None, **kwargs):
        super().__init__(*args,**kwargs)
        self.event_handler_cache = weakref.WeakValueDictionary()
        self.prop_bindings = dict()
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        options = self.base_options
        new_options,media = self.get_options(*args ,**kwargs)
        options.update(new_options)
#        options['hr-seek'] = 'yes'
#        options['hwdec'] = 'vdpau'
#        options['hwdec-preload'] = True
#        options['vo'] = 'opengl-cb'
#        options['opengl_hwdec_interop']='vdpau-glx'
        options['msg-level'] = 'all=status'
        self.new_frame = False

        self.m= self.mpv.Context(**options)
        self.just_die.connect(self.m.shutdown,Q.Qt.DirectConnection)
        self.destroyed.connect(self.just_die,Q.Qt.DirectConnection)

        self.m.set_log_level('terminal-default')
        self.m.set_wakeup_callback_thread(self.onEvent)

        self.m.request_event(self.mpv.EventType.property_change,True)
        self.m.request_event(self.mpv.EventType.video_reconfig,True)
        self.m.request_event(self.mpv.EventType.file_loaded,True)
        self.m.request_event(self.mpv.EventType.log_message,True)

        self.img_width      = 64;#self.mpv.width
        self.img_height     = 64;#self.mpv.height
        self.img_update     = None
        self.setMinimumSize(self.img_width,self.img_height)
        self.tex_id = 0
        self.fbo = None
        self.width = self.img_width
        self.height = self.img_height
        if isinstance(fp, pathlib.Path):
            fp = fp.resolve().absolute().as_posix()
        elif isinstance(fp, Q.QFileInfo):
            fp = fp.canonicalFilePath()
        elif isinstance(fp, Q.QUrl):
            fp = fp.toString()
        if fp:
            self.m.command('loadfile',fp,'append-play',_async=True)

    def command(self,*args, **kwargs):
        self.m.command(*args, **kwargs)

    def try_command(self, *args, **kwargs):
        kwargs.setdefault('_async',True)
        try:
            self.m.command(*args)
        except self.mpv.MPVError:
            pass

#    def set_property(self,prop,*args):
#        self.m.set_property(prop,*args)

    @staticmethod
    def get_options(*args,**kwargs):
        options = kwargs
        media   = list()
        for arg in args:
            if arg.startswith('--'):
                arg,_,value = arg[2:].partition('=')
                options[arg]=value or True
                continue
            media.append(arg)
        return options,media

    @Q.pyqtSlot(object)
    def onEventData(self, event):
        m = self.m
        if not m:
            return
        if event.id is self.mpv.EventType.shutdown:
            print("on_event -> shutdown")
            self.just_die.emit()
        elif event.id is self.mpv.EventType.idle:          self.novid.emit()
        elif event.id is self.mpv.EventType.start_file:    self.hasvid.emit()
#                elif event.id is self.mpv.EventType.file_loaded:   self.durationChanged.emit(m.duration)
        elif event.id is self.mpv.EventType.log_message:   self.logMessage.emit(event.data)
#        print(event.data.text,)
        elif (event.id is self.mpv.EventType.end_file
                or event.id is self.mpv.EventType.video_reconfig):
            try:
                self.m.vid = 1
                self.reconfig.emit( self.m.dwidth, -self.m.dheight )
            except self.mpv.MPVError as ex:
                self.reconfig.emit(None,None)
        elif event.id is self.mpv.EventType.property_change:
            oname = event.data.name
            data  = event.data.data
            if event.reply_userdata:
                try:
                    event.reply_userdata(data)
                except: pass
            elif event.data.name == 'fullscreen':
                pass

    @Q.pyqtSlot()
    def onEvent(self):
        m = self.m
        if not m:
            return
        while True:
            event = m.wait_event(0)
            if event is None:
                print("Warning, received a null event.")
                return
            elif event.id is self.mpv.EventType.none:
                return
            else:
                try:
                    self.onEventData(event)
                except Exception as e:
                    print(e)
    @Q.pyqtSlot()
    def onWakeup(self):
        self.update()

    def initializeGL(self):
        print('initialize GL')
        self.vf = Q.QOpenGLContext.currentContext().versionFunctions(self.pfl)
        self.qctx = Q.QGLContext.currentContext()
        def getprocaddr(name):
            print(name)
            fn = self.qctx.getProcAddress(name.decode('latin1'))
            return fn

        self.ogl = self.m.opengl_cb_context
        self.ogl.init_gl(getprocaddr,None)

        weakref.finalize(self, lambda:self.ogl.set_update_callback(None))
        self.wakeup.connect(self.onWakeup,Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
        self.frameSwapped.connect(lambda:self.ogl.report_flip(self.m.time))
        self.ogl.set_update_callback(self.wakeup.emit)

    def resizeGL(self, w, h):
        self.width  = w
        self.height = h

    def paintGL(self):
        self.ogl.draw(self.defaultFramebufferObject(),self.width,-self.height)

    @Q.pyqtSlot(object)
    def onRequestFile(self, path):
#        print("Setting playlist binding to ", self)
        if self._playlist:
            self._playlist.setPlayer(self)
            self._playlist.onRequestFile(path)

    def mousePressEvent(self,event):
#        print("Setting playlist binding to ", self)
        if self._playlist:
            self._playlist.setPlayer(self)
            super().mousePressEvent(event)

class CtrlPlayer(Q.QWidget):
    vwidth = 540
    vheight = 480
    timeline_precision = 1e-4
    timeline_threshold = 1e-2
    pitch_bend =  1.0
    def reconfig(self,width,height):
        if width > 0 and width < 2**16:
            self.vwidth = width
        if height > 0 and height < 2**16:
            self.vheight= height
        if self.vwidth and self.vheight:
            self.childwidget.setMinimumSize(Q.QSize(self.vwidth,self.vheight))
#        if (not self.sized_once) and width:
#            self.adjustSize()
            self.adjustSize()
            parent = self.parent()
            if parent:
                parent.adjustSize()
                parent = parent.parent()
                if parent:
                    parent.adjustSize()
            self.window().update()
            if not self.sized_once:
                self.sized_once = True
                self.show()

    def novid(self):
        self.sized_once = False
        self.hide()
    def hasvid(self):
        self.sized_once = False
        self.show()
    def speedChanged(self,speed):
        try:
            self.childwidget.m.speed = speed * 1.0/self.speed_base
        except self.childwidget.mpv.MPVError as e:
            pass
    @Q.pyqtSlot(object)
    def onVideo_paramsChanged(self,params):
#        print("video params changed: ",repr(params))
        try:
            self.reconfig(params['w'],params['h'])
        except:
            pass

    @Q.pyqtSlot(object)
    def onSpeedChanged(self,speed):
        if speed * self.speed_base != self.speed.value():
            self.speed.blockSignals(True)
            self.speed.setValue(int(speed * self.speed_base))
            self.speed.blockSignals(False)
    def pause(self):
        self.childwidget.command("cycle","pause")
    def rate_adj(self, val):
        self.speed.setValue(int(self.speed.value() * val))
    def temp_rate(self, factor):
        self.pitch_bend *= factor
        self.speed.setValue(int(self.speed.value() * factor))

    @Q.pyqtSlot()
    def temp_rate_release(self):
        self.speed.setValue(int(self.speed.value() / self.pitch_bend))
        self.pitch_bend = 1.

    @Q.pyqtSlot(int)
    def onTimelineChanged(self,when):
        self.childwidget.try_command("seek", when * self.timeline_precision,"absolute+keyframes")
    def onTimespinChanged(self,when):
        self.childwidget.try_command("seek", when ,"absolute+exact")

#        s = min(max(0.,when * 100./self.timeline_base),100.)
#        self.childwidget.try_command("seek",s,"absolute+exact")

    @Q.pyqtSlot(object)
    def onTime_posChanged(self,time_pos):
        if time_pos:
            cur = self.timeline.value() * self.timeline_precision
            if abs(cur - time_pos) >  self.timeline_threshold:
                self.timeline.blockSignals(True)
                self.timeline.setValue(int(time_pos / self.timeline_precision))
                self.timeline.blockSignals(False)
            cur = self.timespin.value()
            if abs(cur - time_pos) > self.timeline_threshold:
                self.timespin.blockSignals(True)
                self.timespin.setValue(time_pos)
                self.timespin.blockSignals(False)

    @Q.pyqtSlot(object)
    def onDurationChanged(self,dur):
        if dur:
            curr = self.timespin.value()
            self.timespin.blockSignals(True)
            self.timeline.blockSignals(True)
            self.timespin.setRange(0., float(dur))
            self.timespin.setValue(curr)
            self.timeline.setRange(0., int(dur / self.timeline_precision))
            self.timeline.setValue(int(curr/self.timeline_precision))
            self.timespin.blockSignals(False)
            self.timeline.blockSignals(False)
    def __init__(self, *args, **kwargs):
        fp = kwargs.pop('fp',None)
        super().__init__(*args,**kwargs)
        self.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.Frame))
        self.childwidget = AVPlayer(fp=fp,parent=self)
        self.childwidget.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.Label))
        childwidget = self.childwidget
        self.layout = Q.QVBoxLayout()
        self.layout.addWidget(self.childwidget)
        self.setLayout(self.layout)

        time_layout = Q.QVBoxLayout()

        self.timespin= Q.QDoubleSpinBox()
        self.timespin.setFixedWidth(120)
        self.timespin.setDecimals(5)
        self.timespin.setSingleStep(1e-2)
        time_layout.addWidget(self.timespin)

        self.timeline = Q.QSlider(Q.Qt.Horizontal)
        self.timeline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.timeline.setEnabled(True)
        time_layout.addWidget(self.timeline)

        self.layout.addLayout(time_layout)

        self.childwidget.time_pos.valueChanged.connect(self.onTime_posChanged)
        self.timeline.valueChanged.connect(self.onTimelineChanged)
        self.timespin.valueChanged.connect(self.onTimespinChanged)
        self.childwidget.duration.valueChanged.connect(self.onDurationChanged)

        self.speed      = Q.QSlider(Q.Qt.Horizontal)
        self.speed.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.speed_base = 1e8
        self.speed.setValue(self.speed_base)
        self.speed.setRange(16,2*self.speed_base)
        self.speed.setEnabled(True)
        self.speed.valueChanged.connect(self.speedChanged)
        self.childwidget.speed.valueChanged.connect(self.onSpeedChanged)

        play_button = Q.QPushButton("play/pause")
        play_button.clicked.connect(self.pause)
        self.play_button = play_button

        rate_down_button = Q.QPushButton("rate -")
        rate_down_button.clicked.connect(lambda: self.rate_adj(1./1.1))

        rate_down_tmp_button = Q.QPushButton(" tmp -")
        rate_down_tmp_button.pressed.connect(lambda:self.temp_rate(1./1.1))
        rate_down_tmp_button.released.connect(self.temp_rate_release)

        rate_up_button = Q.QPushButton("rate +")
        rate_up_button.clicked.connect(lambda: self.rate_adj(1.1))

        rate_up_tmp_button = Q.QPushButton(" tmp +")
        rate_up_tmp_button.pressed.connect(lambda:self.temp_rate(1.1))
        rate_up_tmp_button.released.connect(self.temp_rate_release)

        rate_down_layout = Q.QVBoxLayout()
        rate_down_layout.addWidget(rate_down_button)
        rate_down_layout.addWidget(rate_down_tmp_button)

        play_speed_layout = Q.QVBoxLayout()
        play_speed_layout.addWidget(play_button)
        play_speed_layout.addWidget(self.speed)

        rate_up_layout = Q.QVBoxLayout()
        rate_up_layout.addWidget(rate_up_button)
        rate_up_layout.addWidget(rate_up_tmp_button)

        control_layout = Q.QHBoxLayout()
        control_layout.addLayout(rate_down_layout)
        control_layout.addLayout(play_speed_layout)
        control_layout.addLayout(rate_up_layout)

        childwidget.video_params.valueChanged.connect(self.onVideo_paramsChanged)
        childwidget.reconfig.connect(self.reconfig)
        childwidget.novid.connect(self.novid)
        self.sized_once = False
        self.reconfig(640,480)
        self.sized_once = False
        childwidget.hasvid.connect(self.hasvid)
#        self.layout.addWidget(self.videocontainer)
        self.layout.addLayout(control_layout)


    @Q.pyqtSlot()
    def openUrl(self):
        urlPath, ok = Q.QInputDialog.getText(self,"Select URL.","ytdl://.....")
        if ok and urlPath:
            print("\n"+urlPath+"\n")
            self.childwidget.try_command("loadfile",str(urlPath),"append-play")

    @Q.pyqtSlot()
    def openFile(self, near = None):
        fileDialog = Q.QFileDialog(self)
        fileDialog.setAcceptMode(Q.QFileDialog.AcceptOpen)
        fileDialog.setFileMode(Q.QFileDialog.ExistingFiles)
        fileDialog.setFilter(Q.QDir.Hidden|Q.QDir.AllEntries|Q.QDir.System)
        fileDialog.setViewMode(Q.QFileDialog.Detail)
        if near is not None:
            if isinstance(near,str):
                near = Q.QFileInfo(near)
            if isinstance(near,Q.QFileInfo):
                if near.isDir():
                    near = Q.QDir(near.filePath())
                else:
                    near = near.dir()
        if not isinstance(near,Q.QDir):
            near = Q.QDir.home()

        fileDialog.setDirectory(near.canonicalPath())
        if fileDialog.exec():
            if fileDialog.selectedFiles():
                for filePath in fileDialog.selectedFiles():
                    print("\n"+filePath+"\n")
                    self.childwidget.try_command("loadfile",str(filePath),"append-play")

class CmdLine(Q.QLineEdit):
    submitted = Q.pyqtSignal(str)
    historyPosChanged = Q.pyqtSignal(int)
    historyChanged = Q.pyqtSignal()
    historyAppended = Q.pyqtSignal(str)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history = list()
        self._history_pos = 0
        self.historyAppended.connect(self.historyChanged)
        self.returnPressed.connect(self.onReturnPressed)
        self.returnPressed.connect(self.onReturnPressed)
    def keyPressEvent(self, evt):
        if evt.modifiers() ==  Q.Qt.ControlModifier:
            if evt.key() == Q.Qt.Key_P:
                if self.historyPos+ 1 < len(self._history):
                    self.historyPos += 1
                    self.setText(self._history[self.historyPos])
                    return
            elif evt.key() == Q.Qt.Key_N:
                if self.historyPos > 0 and self._history:
                    self.historyPos -= 1
                    self.setText(self._history[self.historyPos - 1])
                else:
                    self.historyPos = -1
                    return
            elif evt.key() in (Q.Qt.Key_C, Q.Qt.Key_U):
                self.historyPos = -1
                self.clear()
                return
        super().keyPressEvent(evt)

    @property
    def history(self):
        return self._history

    @property
    def historyPos(self):
        return self._history_pos

    @historyPos.setter
    def historyPos(self,pos):
        new_pos = max(min(len(self._history)-1, int(pos)),-1)
        if new_pos != self._history_pos:
            self._history_pos = new_pos
            if new_pos >= 0:
                self.setText(self.history[new_pos])
            else:
                self.clear()
            self.historyPosChanged.emit(new_pos)

    def historyAppend(self,text):
        self._history.append(text)
#        self._history_pos += 1
        self.historyAppended.emit(text)

    def onReturnPressed(self):
        text = self.text().strip()
        self.historyAppend(text)
        self._history_pos= -1
        self.clear()
        self.historyPosChanged.emit(-1)
        self.submitted.emit(text)

class Canvas(Q.QMainWindow):
    def createPlaylistDock(self):
#        from playlist import PlayList
        self.next_id = 0
#        self.playlist = PlayList(self, None)
        self.propertydock = Q.QDockWidget()
        self.propertydock.setWindowTitle("Playlist")
        self.propertydock.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
        self.propertyview = Q.QTableView(self.propertydock)
        self.propertymodel= AVFlatPropertyModel(player=self.playerwidget,parent=self)
        self.propertyview.setModel(self.propertymodel)
        self.propertydock.setWidget(self.propertyview)
        self.propertydock.show()
#        self.playlistdock.setWidget(self.playlist)

    def __init__(self,*args, fp = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = CtrlPlayer(fp=fp,parent=self)
        self.playerwidget = self.widget.childwidget
        self.setCentralWidget(self.widget)
        self.createPlaylistDock()
        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.propertydock)
        self.propertydock.fileMenu = self.menuBar().addMenu("&File")
        fileMenu = self.propertydock.fileMenu
        fileMenu.addAction("&Open...",self.widget.openFile,"Ctrl+O")
        fileMenu.addAction("O&pen Url...",self.widget.openUrl,"Ctrl+Shift+O")
        fileMenu.addAction("E&xit",self.close,"Ctrl+Q")

        self.toolbar = Q.QDockWidget()
        self.toolbar.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
        toolbargroup = Q.QGroupBox(self.toolbar)
        toolbarlayout= Q.QVBoxLayout()
        histloglayout= Q.QHBoxLayout()
        self.histline= Q.QTextEdit()
        self.histline.setReadOnly(True)
        self.histline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Expanding)
        self.logline= Q.QTextEdit()
        self.logline.setReadOnly(True)
        self.logline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Expanding)

        self.cmdline = cmdline = CmdLine(self.toolbar)
        self.cmdline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        toolbarlayout.addWidget(self.cmdline)
        histloglayout.addWidget(self.histline)
        histloglayout.addWidget(self.logline )
        toolbarlayout.addLayout(histloglayout)
        toolbargroup.setLayout(toolbarlayout)
        self.toolbar.setWidget(toolbargroup)
        self.addDockWidget(Q.Qt.BottomDockWidgetArea,self.toolbar)
        self.toolbar.show()
        cmdline.submitted.connect(self.onCmdlineAccept)
        cmdline.historyChanged.connect(self.redoHistory)
        self.playerwidget.logMessage.connect(self.onLogMessage)
    def redoHistory(self):
        self.histline.clear()
        for h in self.cmdline.history:
            self.histline.append(h)
    def onLogMessage(self, msg):
        self.logline.append('[{}]\t{}:\t{}'.format(msg.level, msg.prefix,msg.text.strip()))

    @Q.pyqtSlot(str)
    def onCmdlineAccept(self, text):
        text = text.split()
#        self.histline.append(' '.join(text))
#        print(*text)
        self.playerwidget.try_command(*text)
#        self.cmdline.clear()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--format')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    fmt = Q.QSurfaceFormat.defaultFormat()
    fmt.setVersion(4,5)
    fmt.setProfile(Q.QSurfaceFormat.CoreProfile)
    fmt.setSamples(4)
    Q.QSurfaceFormat.setDefaultFormat(fmt)

    app = Q.QApplication([])

    mw = Canvas()
    ap = mw.playerwidget
    mw.show()
    mw.raise_()
    for path in args.path:
        ap.m.command('loadfile',path,'append-play')

    app.exec_()
