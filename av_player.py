#! /usr/bin/env python
import signal
from interruptingcow import SignalWakeupHandler
import weakref
import math
import argparse
import shlex
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
import ModernGL
from collections import deque

#import av
import mpv
from av_propertymodel import *
import qtconsole

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
        ,'osc':False
        ,'load_scripts':False
        ,'ytdl':True
        ,'vo':'opengl-cb'
        ,'opengl-fbo-format':'rgba32f'
        ,'alpha':True
#        ,'opengl-es':True
        ,'opengl-swapinterval':1
        ,'opengl-waitvsync':False
        ,'opengl-vsync-fences':6
        ,'tscale-radius':4.0
        ,'tscale-wparam': 1.0
        ,'tscale':'gaussian'
        ,'interpolation':True
        ,'opengl-backend':'x11egl'
        ,'video-sync':'display-resample'
        ,'display-fps':60.0
        ,'interpolation-threshold':0.0
        ,'interpolation':True
        ,'vo-vaapi-scaling':'nla'
        ,'vo-vaapi-scaled-osd':True
        ,'vo-vdpau-hqscaling':5
        ,'vo-vdpau-deint':True
        ,'vd-lavc-fast':True
#        ,'vd-lavc-show-all':True
        ,'hr-seek':'yes'
#        ,'hr-seek-framedrop':True
        ,'hwdec-preload':True
        ,'hwdec':'yes'
        ,'opengl-hwdec-interop':'vaapi-egl'
          }
    _reportFlip = False
    _reportedFlip = False
    _externalDrive = False
    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
    wakeup = Q.pyqtSignal()
    mpv_event = Q.pyqtSignal()
    logMessage = Q.pyqtSignal(object)
    just_die = Q.pyqtSignal()
    paintRateChanged = Q.pyqtSignal(object)
    eventRateChanged = Q.pyqtSignal(object)
    frameRateChanged = Q.pyqtSignal(object)
    swapRateChanged  = Q.pyqtSignal(object)
    mpv = __import__('mpv')

    def get_property(self, prop):
        try: prop_name = self.m.attr_name(prop)
        except: return
        if not prop_name:
            return
        binding = self.findChild(AVProperty, prop_name)
        if binding:
            return binding
        prop_object = AVProperty(prop_name, ctx=self.m,parent=self)
        setattr(self,prop, prop_object)
        if not hasattr(self,prop_name):
            setattr(self,prop_name, prop_object)
        return prop_object

    def __getattr__(self, prop):
        try:
            prop_name = self.m.attr_name(prop)
        except:
#            return super().__getattr__(prop)
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
    def sizeHint(self):
        return Q.QSize(self.img_width,self.img_height)
#        return self.get_property(prop)
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

        self.paintTimes = deque(maxlen=32)
        self.frameTimes = deque(maxlen=32)
        self.swapTimes  = deque(maxlen=32)
        self.eventTimes = deque(maxlen=32)
        self.setMouseTracking(True)
        self._updated = False
        self.event_handler_cache = weakref.WeakValueDictionary()
        self.prop_bindings = dict()
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        options = self.base_options.copy()
        new_options,media = self.get_options(*args ,**kwargs)
        options.update(new_options)
        options['msg-level'] = 'all=status,vd=debug,hwdec=debug,vo=debug,video=v,opengl=debug'
        options['af']='rubberband=channels=apart:pitch=quality'
        self.new_frame = False

        mpv = self.mpv
        self.m= mpv.Context(**options)
        m = self.m
        self.just_die.connect(m.shutdown,Q.Qt.DirectConnection)
        self.destroyed.connect(self.just_die,Q.Qt.DirectConnection)

        self.m.set_log_level('terminal-default')
        self.m.set_wakeup_callback_thread(self.onEvent)
        self.m.request_event(self.mpv.EventType.property_change,True)
        self.m.request_event(self.mpv.EventType.video_reconfig,True)
        self.m.request_event(self.mpv.EventType.file_loaded,True)
        self.m.request_event(self.mpv.EventType.log_message,True)

        self.img_width      = 64
        self.img_height     = 64
        self.img_update     = None

        self.tex_id = 0
        self.fbo = None
        self._width = self.img_width
        self._height = self.img_height
        if isinstance(fp, pathlib.Path):
            fp = fp.resolve().absolute().as_posix()
        elif isinstance(fp, Q.QFileInfo):
            fp = fp.canonicalFilePath()
        elif isinstance(fp, Q.QUrl):
            fp = fp.toString()
        Q.QTimer.singleShot(0, self.update)
        if fp:
            Q.QTimer.singleShot(0,(lambda : self.m.command('loadfile',fp,'append',_async=True)))

    def command(self,*args, **kwargs):
        self.m.command(*args, **kwargs)

    def command_string(self, cmdlist):
        try: self.m.command_string(cmdlist)
        except: pass

    def try_command(self, *args, **kwargs):
        kwargs.setdefault('_async',True)
        try: self.m.command(*args)
        except self.mpv.MPVError: pass

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

    @Q.pyqtProperty(float)
    def paintRate(self):
        if len(self.paintTimes) < 2:
            return 0
        else:
            return 1e6 * (len(self.paintTimes)-1) / (self.paintTimes[-1] - self.paintTimes[0])

    def paintTimeAppend(self, time):
        self.paintTimes.append(time)
        self.paintRateChanged.emit(self.paintRate)

    @Q.pyqtProperty(float)
    def frameRate(self):
        if len(self.frameTimes) < 2:
            return 0
        else:
            return 1e6 * (len(self.frameTimes)-1) / (self.frameTimes[-1] - self.frameTimes[0])

    def frameTimeAppend(self, time):
        self.frameTimes.append(time)
        self.frameRateChanged.emit(self.frameRate)

    @Q.pyqtProperty(float)
    def swapRate(self):
        if len(self.swapTimes) < 2:
            return 0
        else:
            return 1e6 * (len(self.swapTimes)-1) / (self.swapTimes[-1] - self.swapTimes[0])

    def swapTimeAppend(self, time):
        self.swapTimes.append(time)
        self.swapRateChanged.emit(self.swapRate)


    @Q.pyqtProperty(float)
    def eventRate(self):
        if len(self.eventTimes) < 2:
            return 0
        else:
            return 1e6 * (len(self.eventTimes) - 1 )/ (self.eventTimes[-1][0] - self.eventTimes[0][0])

    def eventTimeAppend(self, time, type=None):
        self.eventTimes.append((time,type))
        self.eventRateChanged.emit(self.eventRate)


    @Q.pyqtSlot(object)
    def onEventData(self, event):
        m = self.m
        if not m:
            return
        self.eventTimeAppend(self.m.time,event.id)
        if event.id is self.mpv.EventType.shutdown:
            print("on_event -> shutdown")
            self.just_die.emit()
        elif event.id is self.mpv.EventType.idle:          self.novid.emit()
        elif event.id is self.mpv.EventType.start_file:    self.hasvid.emit()
        elif event.id is self.mpv.EventType.file_loaded:
            ao = m.ao
            if ao and ao[0]['name'] in ('null','none'):
                m.aid = 0
            else:
                try:
                    if m.current_ao in ('null' ,'none'):
                        m.aid = 0
                except self.mpv.MPVError as e:
                    if e.code == self.mpv.Error.property_unavailable:
                        m.aid = 0

            if not m.aid:
                if m.af:
                    self.af = m.af
                m.af = ""
            else:
                if self.af and not m.af:
                    m.af = self.af
#c            if not m.aid:
 #               m.video_sync = 'audio'
 #           else:
#                m.video_sync = 'display-resample'
#        self.durationChanged.emit(m.duration)
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
                except:
                    pass
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
#        if not self._externalDrive:
        self.frameTimeAppend(self.m.time)
        self.update()

    def initializeGL(self):
        print('initialize GL')
#        self._vf = Q.QOpenGLContext.currentContext().versionFunctions(self.pfl)
        self.mctx = ModernGL.create_context()
        def getprocaddr(name):
            return self.mctx.mglo.get_proc_address(name.decode('latin1'))
        self.ogl = self.m.opengl_cb_context
        self.ogl.init_gl(getprocaddr,None)
#        self.m.opengl_fbo_format = 'rgba32f'
#        self.m.alpha = True

        weakref.finalize(self, lambda:self.ogl.set_update_callback(None))
        self.wakeup.connect(self.onWakeup,Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
        self.frameSwapped.connect(self.onFrameSwapped)
        self.ogl.set_update_callback(self.wakeup.emit)

    @Q.pyqtSlot()
    def onFrameSwapped(self):
        self.swapTimeAppend(self.m.time)
        if self._updated:
            self._updated = False
        if self.reportFlip:
            self.ogl.report_flip(self.m.time)
            self._reportedFlip = True

    @property
    def reportFlip(self):
        return self._reportFlip

    @reportFlip.setter
    def reportFlip(self, val):
        if self._reportedFlip:
            return
        self._reportFlip = bool(val)

    @property
    def externalDrive(self):
        return self._externalDrive

    @externalDrive.setter
    def externalDrive(self, val):
        self._externalDrive = bool(val)

    def resizeGL(self, w, h):
        self._width  = w
        self._height = h

    def paintGL(self):
        self.paintTimeAppend(self.m.time)
        self.ogl.draw(self.defaultFramebufferObject(),self._width,-self._height)
        self._updated = True


#    @Q.pyqtSlot(object)
#    def onRequestFile(self, path):
#        print("Setting playlist binding to ", self)
#        if self._playlist:
#            self._playlist.setPlayer(self)
#            self._playlist.onRequestFile(path)
#    def mousePressEvent(self,event):
#        btn = 0 if (event.buttons() & Q.Qt.LeftButton) else 1
#        self.m.command('mouse',event.x(),self._height-event.y(),btn, 'single',_async=True)
#        event.ignore()
#
#    def mouseDoubleClickEvent(self,event):
#        btn = 0 if (event.buttons() & Q.Qt.LeftButton) else 1
#        self.m.command('mouse',event.x(),self._height-event.y(),btn, 'double',_async=True)
#        event.ignore()

#    def mouseMoveEvent(self,event):
#        self.m.command('mouse',event.x(),event.y(),_async=True)
#        event.ignore()

#        print("Setting playlist binding to ", self)
#        if self._playlist:
#            self._playlist.setPlayer(self)
#            super().mousePressEvent(event)
class CmdLine(Q.QLineEdit):
    submitted = Q.pyqtSignal(str,bool)
    historyPosChanged = Q.pyqtSignal(int)
    historyChanged = Q.pyqtSignal()
    historyAppended = Q.pyqtSignal(str)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history = collections.deque()
        self._history_pos = 0
        self.historyAppended.connect(self.historyChanged)
        self.returnPressed.connect(self.onReturnPressed)
        self.returnPressed.connect(self.onReturnPressed)
    def keyPressEvent(self, evt):
        if evt.modifiers() ==  Q.Qt.ControlModifier:
            if evt.key() == Q.Qt.Key_P or evt.key() == Q.Qt.Key_Up:
                if self.historyPos+ 1 < len(self._history):
                    self.historyPos += 1
                    self.setText(self._history[self.historyPos])
                    return
            elif evt.key() == Q.Qt.Key_N or evt.key() == Q.Qt.Key_Down:
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
        if(text):
            self._history.appendleft(text)
            self.historyAppended.emit(text)

    def onReturnPressed(self):
        text = self.text().strip()
        if self._history and self._history[0] == text:
            text = ''
        if text:
            self.historyAppend(text)
            self._history_pos= -1
            self.clear()
            self.historyPosChanged.emit(-1)
            self.submitted.emit(text, False)
        elif self._history:
            self._history_pos= -1
            self.clear()
            self.historyPosChanged.emit(-1)
            self.submitted.emit(self._history[0], False)

class CtrlPlayer(Q.QWidget):
    vwidth = 640
    vheight = 480
    timeline_precision = 1e-4
    timeline_threshold = 1e-3
    pitch_bend =  1.0

    def reconfig(self,width,height):
        if width > 0 and width < 2**16:
            self.vwidth = width
        if height > 0 and height < 2**16:
            self.vheight= height
        if self.vwidth and self.vheight:
            self.childwidget.img_width = self.vwidth
            self.childwidget.img_height = self.vheight
            if (not self.sized_once) and width:
                self.childwidget.setMinimumSize(Q.QSize(self.vwidth,self.vheight))
                self.adjustSize()
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

    @property
    def timelineThreshold(self):
        if self.childwidget:
            fps = self.childwidget.container_fps.value()
            if fps:
                return max(self.timeline_threshold, 1. / fps)
        return self.timeline_threshold

    @Q.pyqtSlot(int)
    def onTimelineChanged(self,when):
        when *= self.timeline_precision
        cur = self.childwidget.time_pos.value()
        threshold = self.timelineThreshold

        if self.timeline.isSliderDown():
            if not self.childwidget.seeking.value():
                if abs(when - cur) > threshold:
                    self.childwidget.try_command("seek", when,"absolute+exact")
        else:
            if abs(when - cur) > threshold:
                self.childwidget.try_command("seek", when,"absolute+exact")

    def onTimespinChanged(self,when):
        when
        cur = self.childwidget.time_pos.value()
        threshold = self.timelineThreshold

        if abs(cur - when) >  threshold:
            self.childwidget.try_command("seek", when ,"absolute+exact")

    @Q.pyqtSlot(object)
    def onTime_posChanged(self,time_pos):
        if time_pos:
            threshold = self.timelineThreshold
            cur = self.timeline.value() * self.timeline_precision
            if self.timeline.isSliderDown():
                if abs(cur - time_pos) >  threshold:
                    self.onTimelineChanged(self.timeline.value())
            else:
                if abs(cur - time_pos) >  threshold:
                    self.timeline.blockSignals(True)
                    self.timeline.setValue(int(time_pos / self.timeline_precision))
                    self.timeline.blockSignals(False)
            cur = self.timespin.value()
            if abs(cur - time_pos) > threshold:
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
        use_tabs = kwargs.pop('tabs',True)
        super().__init__(*args,**kwargs)
        self.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.Frame))
        childwidget = self.childwidget = AVPlayer(fp=fp,parent=self)
        childwidget.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.MinimumExpanding
          , Q.QSizePolicy.Label))

        self.splitter = Q.QSplitter()
        self.splitter.setOrientation(Q.Qt.Vertical)
        self.layout = Q.QVBoxLayout()
        self.splitter.addWidget(self.childwidget)
        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)

        controls_widget = Q.QWidget()
        controls_layout = Q.QVBoxLayout()
        controls_widget.setLayout(controls_layout)
        self.splitter.addWidget(controls_widget)
        time_layout = Q.QVBoxLayout()

        timespin_layout = Q.QHBoxLayout()

        self.timespin= Q.QDoubleSpinBox()
        self.timespin.setFixedWidth(120)
        self.timespin.setDecimals(5)
        self.timespin.setSingleStep(1e-2)
        timespin_layout.addWidget(self.timespin)

        step_back = Q.QPushButton("step -")
        step_back.clicked.connect(lambda : self.childwidget.try_command('frame-back-step'))
        timespin_layout.addWidget(step_back)

        step_forward = Q.QPushButton("step +")
        step_forward.clicked.connect(lambda : self.childwidget.try_command('frame-step'))
        timespin_layout.addWidget(step_forward)

        timespin_layout.addStretch(-1)

        time_layout.addLayout(timespin_layout)

        self.timeline = Q.QSlider(Q.Qt.Horizontal)
        self.timeline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.timeline.setEnabled(True)
        self.timeline.sliderReleased.connect(lambda : self.onTimelineChanged(self.timeline.value()))
        time_layout.addWidget(self.timeline)

        controls_layout.addLayout(time_layout)

        childwidget.time_pos.valueChanged.connect(self.onTime_posChanged)
        self.timeline.valueChanged.connect(self.onTimelineChanged)
        self.timespin.valueChanged.connect(self.onTimespinChanged)
        childwidget.duration.valueChanged.connect(self.onDurationChanged)

        self.speed      = Q.QSlider(Q.Qt.Horizontal)
        self.speed.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.speed_base = 1e8
        self.speed.setValue(self.speed_base)
        self.speed.setRange(16,2*self.speed_base)
        self.speed.setEnabled(True)
        self.speed.valueChanged.connect(self.speedChanged)
        childwidget.speed.valueChanged.connect(self.onSpeedChanged)

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
        childwidget.hasvid.connect(self.hasvid)
        self.sized_once = False
        self.reconfig(640,480)
        self.sized_once = False

        controls_layout.addLayout(control_layout)

#        self.toolbargroup = toolbargroup = Q.QGroupBox()

        toolbarlayout= Q.QVBoxLayout()
        cmdlinelayout= Q.QHBoxLayout()
        histloglayout= Q.QHBoxLayout()
        self.histline= Q.QPlainTextEdit()
        self.histline.setReadOnly(True)
        self.histline.setCenterOnScroll(False)
        self.histline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.logline= Q.QPlainTextEdit()
        self.logline.setReadOnly(True)
        self.logline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)

        self.cmdline = cmdline = CmdLine()
        er_label = self.er_label = Q.QLabel()
        pr_label = self.pr_label = Q.QLabel()
        fr_label = self.fr_label = Q.QLabel()
        sr_label = self.sr_label = Q.QLabel()
        self._timer = Q.QTimer(self)
        self._timer.setInterval(int(1000/5))
        self._timer.setTimerType(Q.Qt.PreciseTimer)

        self._timer.timeout.connect(lambda :self.pr_label.setText('paint rate: {:.6f}'.format(self.childwidget.paintRate)))
        self._timer.timeout.connect(lambda :self.er_label.setText('event rate: {:.6f}'.format(self.childwidget.eventRate)))
        self._timer.timeout.connect(lambda :self.fr_label.setText('frame rate: {:.6f}'.format(self.childwidget.frameRate)))
        self._timer.timeout.connect(lambda :self.sr_label.setText('swap rate: {:.6f}'.format(self.childwidget.swapRate)))
        self._timer.start()
#        self.cmdline = cmdline = CmdLine(self.toolbargroup)
        self.cmdline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        cmdlinelayout.addWidget(self.cmdline)
        cmdlinelayout.addWidget(er_label)
        cmdlinelayout.addWidget(pr_label)
        cmdlinelayout.addWidget(fr_label)
        cmdlinelayout.addWidget(sr_label)
        toolbarlayout.addLayout(cmdlinelayout)
        histloglayout.addWidget(self.histline)
        histloglayout.addWidget(self.logline )

        if use_tabs:
            tw = Q.QTabWidget(parent=self)
            tg = Q.QWidget()
            tg.setLayout(histloglayout)
            tw.addTab(tg,"history/log")
            childwidget._property_model = AVTreePropertyModel(player=childwidget,parent=childwidget)
            tv = Q.QTreeView()
            tv.setModel(childwidget._property_model)
            tw.addTab(tv,"properties")
            tw.setVisible(True)
            toolbarlayout.addWidget(tw)
        else:
            toolbarlayout.addLayout(histloglayout)
#        toolbargroup.setLayout(toolbarlayout)
        controls_layout.addLayout(toolbarlayout)
        cmdline.submitted.connect(self.onCmdlineAccept,Q.Qt.UniqueConnection|Q.Qt.AutoConnection)
        cmdline.historyChanged.connect(self.redoHistory)
        self.childwidget.logMessage.connect(self.onLogMessage)

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

    def redoHistory(self):
        self.histline.clear()
        tc = self.histline.textCursor()
        tc.movePosition(tc.End,tc.MoveAnchor)
        self.histline.setTextCursor(tc)

        for h in reversed(self.cmdline.history):
            tc.insertText(h)
            tc.insertText('\n')
        self.histline.ensureCursorVisible()

    def onLogMessage(self, msg):
        tc = self.logline.textCursor()
        tc.movePosition(tc.End,tc.MoveAnchor)
        self.logline.setTextCursor(tc)
        tc.insertText('[{}]\t{}:\t{}'.format(msg.level, msg.prefix,msg.text).strip())
        tc.insertText('\n')
#        self.logline.ensureCursorVisible()

    @Q.pyqtSlot(str,bool)
    def onCmdlineAccept(self, text, append = False):
        if append:
            tc = self.histline.textCursor()
            tc.movePosition(tc.End,tc.MoveAnchor)
            self.histline.setTextCursor(tc)
            tc.insertText(text)
            tc.insertText('\n')
        self.childwidget.command_string(text)
        self.histline.ensureCursorVisible()
#        self.redoHistory()

class Canvas(Q.QMainWindow):
    _use_tree = True
    _use_table= True

    def createPlaylistDock(self):
#        from playlist import PlayList
        self.next_id = 0
#        self.playlist = PlayList(self, None)
        self.propertydock = Q.QDockWidget()
        self.propertydock.setWindowTitle("Playlist")
        self.propertydock.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
        tw = Q.QTabWidget(parent=self.propertydock)
        player = self.playerwidget
        player._property_model = AVTreePropertyModel(player=player, parent=player)
        if self._use_tree:
            tv = Q.QTreeView()
            tv.setModel(player._property_model)
            tw.addTab(tv,'tree')
            tv.header().setSectionResizeMode(Q.QHeaderView.Stretch)

#        player._flat_model     = AVFlatPropertyModel(player=player, parent=player)
#        if self._use_table:
#            self.propertymodel= AVFlatPropertyModel(player=self.playerwidget,parent=self)
#            self.propertyview = Q.QTableView(self.propertydock)
#            self.propertyview.setModel(player._flat_model)
#            tw.addTab(self.propertyview, 'table')
#            self.propertyview.horizontalHeader().setSectionResizeMode(Q.QHeaderView.Stretch)

        self.propertydock.setWidget(tw)
        tw.show()
        tw.parent().adjustSize()
        tw.parent().update()
        self.propertydock.show()
#        self.playlistdock.setWidget(self.playlist)

    def __init__(self,*args, fp = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = Q.QTimer()
#        self._timer.setInterval(int(1000/30))
        self._timer.setTimerType(Q.Qt.PreciseTimer)

        tw = Q.QTabWidget(parent=self)
        cw = CtrlPlayer(*args, parent=self, **kwargs)
        tw.addTab(cw,"video")
        cw.childwidget.resize(self.size())
        player = cw.childwidget
#        player._property_model = AVTreePropertyModel(player=player,parent=player)
#        tv = Q.QTreeView()
#        tv.setModel(player._property_model)
#        tw.addTab(tv,"properties")
        tw.setVisible(True)
        self.widget = cw
        self.playerwidget = player

#        self._timer.timeout.connect(self.update)
#        self._timer.timeout.connect(cw.update)
        self._timer.timeout.connect(cw.childwidget.update)

#        self.widget = CtrlPlayer(fp=fp,parent=self)
#        self.playerwidget = self.widget.childwidget
        self.setCentralWidget(tw)

#        self.toolbar = Q.QDockWidget()
#        self.toolbar.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
#        self.toolbar.setWidget(toolbargroup)
#        self.addDockWidget(Q.Qt.BottomDockWidgetArea,self.toolbar)
#        self.toolbar.show()

#    def finishPlaylist(self):
#        self.createPlaylistDock()
#        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.propertydock)
#        self.propertydock.fileMenu =
        fileMenu = self.menuBar().addMenu("&File")
#        fileMenu = self.propertydock.fileMenu
        fileMenu.addAction("&Open...",self.widget.openFile,"Ctrl+O")
        fileMenu.addAction("O&pen Url...",self.widget.openUrl,"Ctrl+Shift+O")
        fileMenu.addAction("E&xit",self.close,"Ctrl+Q")

    @property
    def forcedFrameRate(self):
        if self._timer.interval():
            return 10000 / self._timer.interval()

    @forcedFrameRate.setter
    def forcedFrameRate(self, val):
        if val:
            self._timer.setInterval(int(1000/float(val)))
            self.playerwidget.externalDrive= True
            self._timer.start()
            self._timer.timeout.connect(self.update,Q.Qt.UniqueConnection)
        else:
            self._timer.stop()
            self.playerwidget.externalDrive= False
            try:
                self._timer.timeout.disconnect()
            except:
                pass
#            self.playerwidget.reportFlip = True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--format')
    parser.add_argument('path', nargs='+')
    parser.add_argument('--extra',default=None,action='store')
    parser.add_argument('--forcerate',type=float,default=None)
    parser.add_argument('--nrf','--no-reportflip',action='store_true')

    args = parser.parse_args()

#    fmt = Q.QSurfaceFormat.defaultFormat()
#    fmt.setVersion(4,5)
#    fmt.setProfile(fmt.CoreProfile)
#    fmt.setDepthBufferSize(24)
#    fmt.setRedBufferSize(8)
#    fmt.setGreenBufferSize(8)
#    fmt.setBlueBufferSize(8)
#    fmt.setAlphaBufferSize(8)
#    fmt.setSwapBehavior(fmt.TripleBuffer)
#    fmt.setSwapBehavior(fmt.SingleBuffer)
#    fmt.setRenderableType(fmt.OpenGL)
#    fmt.setOption(fmt.DeprecatedFunctions,False)
#    fmt.setOption(fmt.ResetNotification,True)
#    Q.QSurfaceFormat.setDefaultFormat(fmt)

#    Q.QCoreApplication.setAttribute(Q.Qt.AA_ShareOpenGLContexts)

    app = Q.QApplication([])

    mw = Canvas()
    if args.forcerate is not None and args.forcerate:
        mw.forcedFrameRate = args.forcerate
#    else:
#        mw.forcedFrameRate = None

    ap = mw.playerwidget
    fmt = Q.QOpenGLContext.globalShareContext().format()
    print('OpenGLFormat:\n')
    print('version={}'.format(fmt.version()))
    print('samples={}'.format(fmt.samples()))
    print('redBufferSize={}'.format(fmt.redBufferSize()))
    print('greenBufferSize={}'.format(fmt.greenBufferSize()))
    print('blueBufferSize={}'.format(fmt.blueBufferSize()))
    print('alphaBufferSize={}'.format(fmt.alphaBufferSize()))
    print('depthBufferSize={}'.format(fmt.depthBufferSize()))
    print('stencilBufferSize={}'.format(fmt.stencilBufferSize()))
    print('swapBehavior={}'.format(fmt.swapBehavior()))
    print('swapInterval={}'.format(fmt.swapInterval()))
    print('debugContext={}'.format(fmt.testOption(fmt.DebugContext)))
    print('deprecatedFunctions={}'.format(fmt.testOption(fmt.DeprecatedFunctions)))
    print('renderable={}'.format(fmt.renderableType()))

    del fmt

    if args.nrf:
        ap.reportFlip = False
    else:
        ap.reportFlip = True

#    if args.reportflip:
#        ap.reportFlip = True
    mw.show()
    mw.raise_()
    if args.extra:
        extra = args.extra.split()
        for e in extra:
            if '=' in e:
                a,_,b = e.partition('=')
                ap.m.set_property(a,b)
    for path in args.path:
        if '=' in path:
            a,_,b = path.partition('=')
            ap.m.set_property(a,b)
        else:
            ap.m.command('loadfile',path,'append-play')
#    import IPython, ipykernel, threading
#    kt = threading.Thread(target=IPython.embed)
#    kt.start()
#    qc = ipykernel.connect_qtconsole()
#    IPython.embed_kernel()
    with SignalWakeupHandler(app):
        signal.signal(signal.SIGINT, lambda *a:app.quit())
#        IPython.embed()
#        Q.QTimer.singleShot(0,IPython.embed)
        sys.exit(app.exec_())
