#! /usr/bin/env python
import signal
from interruptingcow import SignalWakeupHandler
import weakref
import math
import argparse
import shlex
import functools
import pathlib
import struct, array
import os
import sys
import pprint
import time
import collections
from qtproxy import Q

from collections import deque,defaultdict

#import av
import mpv
from av_propertymodel import *
import qtconsole


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
#            self._value = value
            self.context.set_property(self.objectName(),value)
#            setattr(self.context,self.objectName(),value)

    @Q.pyqtSlot(object)
    def _emitValueChanged(self, value):
#        if value is None:
#            value = self.context.try_get_property(self.objectName(),None)
        if self._value != value:
            self._value = value
            self.valueChanged.emit(value)

    @Q.pyqtSlot()
    def forceUpdate(self):
        value = self.context.try_get_property(self.objectName(),None)
        if value is not None:
            self._value = value
            self.valueChanged.emit(value)

#        self._emitValueChanged(self.context.try_get_property(self.objectName(),None))

    def __index__(self):
        return int(self)

    def __str__(self):
        return str(self.value())

    def __bytes__(self):
        return bytes(self.value())

    def __init__(self, prop, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__context__  = ctx
        _prop = ctx.attr_name(prop)
        if _prop is None:
            raise ValueError("invalid property to observe, {}".format(prop))
        prop = _prop
        self.setObjectName(prop)
#        ctx.request_event(ctx.mpv.EventType.property_change,True)
        self._value = None
        self.forceUpdate()

        reply_userdata = self._emitValueChanged
        ctx_ref = weakref.ref(ctx)
#        prop = (prop,None)
        def unobserve_cb(val,prop):
            ctx = ctx_ref()
            try:
                ctx.unobserve_property(data=val,prop=prop)
            except:
                pass
        self.reply_userdata = reply_userdata
        ctx.observe_property(prop,reply_userdata)
        self._finalizer = weakref.finalize(self,unobserve_cb, reply_userdata,prop)

class AVPlayer(Q.QOpenGLWidget):
    pfl = Q.QOpenGLVersionProfile()
    pfl.setVersion(4,1)
    pfl.setProfile(Q.QSurfaceFormat.CoreProfile)

    _get_proc_address_ctypes = None
    _get_proc_address_qt     = None

    @classmethod
    def get_proc_address_ctypes(cls):
        if not cls._get_proc_address_ctypes:
            import ctypes,ctypes.util
            lgl = ctypes.cdll.LoadLibrary(ctypes.util.find_library('GL'))
            get_proc_address = lgl.glXGetProcAddress
            get_proc_address.restype = ctypes.c_void_p
            get_proc_address.argtypes = [ ctypes.c_char_p ]
            cls._get_proc_address_ctypes = lambda name: get_proc_address(name if isinstance(name,bytes) else name.encode('latin1'))
        return cls._get_proc_address_ctypes

    @classmethod
    def get_proc_address_qtgl(cls):
        get_proc_address = Q.QGLContext.currentContext().getProcAddress
        return lambda name: int(get_proc_address(name.decode('latin1') if isinstance(name,bytes) else name))

    base_options = {
         'load-unsafe-playlists':True
        ,'prefetch-playlist':True
        ,'input-default-bindings':False
        ,'input_vo_keyboard':False
        ,'keep_open':True
        ,'gapless_audio':True
        ,'osc':False
        ,'load_scripts':False
        ,'ytdl':True
        ,'vo':'libmpv'
        ,'opengl-fbo-format':'rgba16'
        ,'alpha':'no'
        ,'opengl-es':'auto'
        ,'opengl-swapinterval':1
        ,'opengl-waitvsync':False
#        ,'opengl-vsync-fences':6
        ,'tscale-radius':4.0
        ,'tscale-wparam': 1.0
        ,'tscale':'gaussian'
#        ,'scale':'spline36'
#        ,'sws-scaler':'sinc'
        ,'interpolation':True
        ,'video-sync':'display-resample'
        ,'display-fps':60.0
        ,'interpolation-threshold':0.0
        ,'interpolation':True
        ,'vo-vaapi-scaling':'hq'
#        ,'vo-vaapi-scaled-osd':True
#        ,'vo-vdpau-hqscaling':9
        ,'audio-pitch-correction':True
        ,'video-timing-offset':0
        ,'video-latency-hacks':True
        ,'pulse-latency-hacks':False
#        ,'pulse-buffer':1024
#        ,'audio-buffer':0.125
#        ,'vd-lavc-fast':True
#        ,'vd-lavc-show-all':True
        ,'hr-seek':'yes'
        ,'hr-seek-framedrop':False
        ,'hwdec-preload':True
        ,'hwdec':'yes'
        ,'opengl-backend':'drm'
        ,'gpu-hwdec-interop':'drmprime-drm'
          }
    _reportFlip = False
    _reportedFlip = False
    _timesWindow = 1e6
    _externalDrive = False
    _get_proc_address = 'ctypes'
    _get_proc_address_debug = True
    ogl = None
#    _property_model = None

    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
    wakeup = Q.pyqtSignal()
    doWakeup = Q.pyqtSignal(object)
    mpv_event = Q.pyqtSignal()
    logMessage = Q.pyqtSignal(object)
    just_die = Q.pyqtSignal()
    propertyModelChanged = Q.pyqtSignal(object)
#    paintRateChanged = Q.pyqtSignal(object)
#    eventRateChanged = Q.pyqtSignal(object)
#    frameRateChanged = Q.pyqtSignal(object)
#    swapRateChanged  = Q.pyqtSignal(object)
    openglInitialized = Q.pyqtSignal(object)
    mpv = __import__('mpv')

    def get_property(self, prop):
        try:
            prop_name = self.m.attr_name(prop)
        except:
            return
        if not prop_name:
            return
        binding = self.findChild(AVProperty, prop_name)
        if binding:
            return binding
        prop_object = AVProperty(prop_name, ctx=self.m,parent=self)
        if not hasattr(self, prop):
            setattr(self,prop, prop_object)
        if not hasattr(self,prop_name):
            setattr(self,prop_name, prop_object)
        return prop_object

    def __getattr__(self, prop):
        try:
            prop_name = self.m.attr_name(prop)
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

    def sizeHint(self):
        return Q.QSize(self.img_width,self.img_height)

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

        self.setSizePolicy(Q.QSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Expanding))
        self.paintTimes = deque(maxlen=32)
        self.frameTimes = deque(maxlen=32)
        self.swapTimes  = deque(maxlen=32)
        self.eventTimes = deque(maxlen=2000)
        self.setMouseTracking(True)
        self._updated = False
        self._timesWindow = 1e6
        self.event_handler_cache = weakref.WeakValueDictionary()
        self.prop_bindings = dict()
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        options = self.base_options.copy()
        new_options,media = self.get_options(*args ,**kwargs)
        options.update(new_options)
        options['msg-level'] = 'all=status,cplayer=error,video=debug,vd=trace,hwdec=debug,vf=debug,vo=trace,,opengl=trace,af=debug,ao=debug'
#        options['af']='rubberband=channels=apart:pitch=quality'
        self.new_frame = False

        mpv = self.mpv
        print('options:',options)
        m = self.m = mpv.Context(**options)
#        self.just_die.connect(m.shutdown,Q.Qt.DirectConnection)
        self.destroyed.connect(self.just_die,Q.Qt.DirectConnection)
        self.destroyed.connect(lambda:(m.set_wakeup_callback(None),m.shutdown()),Q.Qt.DirectConnection)


        for t in mpv.EventType:
            self.m.request_event(t, t not in (mpv.EventType.tick,mpv.EventType.none))
        self.m.request_event(self.mpv.EventType.property_change,True)
        self.m.request_event(self.mpv.EventType.video_reconfig,True)
        self.m.request_event(self.mpv.EventType.audio_reconfig,True)
        self.m.request_event(self.mpv.EventType.seek,True)
        self.m.request_event(self.mpv.EventType.command_reply,True)
        self.m.request_event(self.mpv.EventType.set_property_reply,True)
        self.m.request_event(self.mpv.EventType.file_loaded,True)
        self.m.request_event(self.mpv.EventType.log_message,True)

        self.m.set_log_level('terminal-default')
#        self.m.set_wakeup_callback(self.onEvent)
        self.m.msg_level='all=status,cplayer=error,video=debug,vd=trace,hwdec=debug,vf=debug,vo=trace,,opengl=trace,af=debug,ao=debug'

        self.mpv_event.connect(self.onEvent,Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
#        self.m.set_wakeup_callback(self.mpv_event.emit)
#        self.m.set_wakeup_callback_thread(self.onEvent,maxsize=0)
        self.m.set_wakeup_callback_thread(self.onEvent,maxsize=4)

        self.m.request_event(self.mpv.EventType.property_change,True)
        self.m.request_event(self.mpv.EventType.video_reconfig,True)
        self.m.request_event(self.mpv.EventType.audio_reconfig,True)
        self.m.request_event(self.mpv.EventType.seek,True)
        self.m.request_event(self.mpv.EventType.command_reply,True)
        self.m.request_event(self.mpv.EventType.set_property_reply,True)
        self.m.request_event(self.mpv.EventType.file_loaded,True)
        self.m.request_event(self.mpv.EventType.log_message,True)

        self.img_width      = 64
        self.img_height     = 64
        self.img_update     = None

        self.tex_id = 0
        self.fbo = None
        self._width = self.img_width
        self._height = self.img_height

        self._property_model = AVTreePropertyModel(player=self,parent=self)

        if isinstance(fp, pathlib.Path):
            fp = fp.resolve().absolute().as_posix()
        elif isinstance(fp, Q.QFileInfo):
            fp = fp.canonicalFilePath()
        elif isinstance(fp, Q.QUrl):
            fp = fp.toString()
        Q.QTimer.singleShot(1, self.update)
        if fp:
            Q.QTimer.singleShot(0,(lambda : self.try_command('loadfile',fp,'append-play',_async=False)))

    def command(self,*args, **kwargs):
        self.m.command(*args, **kwargs)

    def command_string(self, cmdlist):
        try: self.m.command_string(cmdlist)
        except: pass

    def try_command(self, *args, **kwargs):
        kwargs.setdefault('_async',True)
        try: self.m.command(*args)
        except self.mpv.MPVError: pass

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
#        time = self.paintTimes[-1]
#        while len(self.paintTimes) > 2 and self.paintTimes[0] < time - self._timesWindow:
#            self.paintTimes.popleft()
        return 1e6 * (len(self.paintTimes)-1) / (self.paintTimes[-1] - self.paintTimes[0])

    def paintTimeAppend(self, time):
        while self.paintTimes and self.paintTimes[0] < time - self._timesWindow:
            self.paintTimes.popleft()
        self.paintTimes.append(time)
#        self.paintRateChanged.emit(self.paintRate)

    @Q.pyqtProperty(float)
    def frameRate(self):
        if len(self.frameTimes) < 2:
            return 0
#        time = self.frameTimes[-1]
#        while len(self.paintTimes) > 2 and self.paintTimes[0] < time - self._timesWindow:
#            self.paintTimes.popleft()
        return 1e6 * (len(self.frameTimes)-1) / (self.frameTimes[-1] - self.frameTimes[0])

    def frameTimeAppend(self, time):
        while self.frameTimes and self.frameTimes[0] < time - self._timesWindow:
            self.frameTimes.popleft()
        self.frameTimes.append(time)
#        self.frameRateChanged.emit(self.frameRate)

    @Q.pyqtProperty(float)
    def swapRate(self):
        if len(self.swapTimes) < 2:
            return 0
#        time = self.swapTimes[-1]
#        while len(self.swapTimes) > 2 and self.swapTimes[0] < time - self._timesWindow:
#            self.swapTimes.popleft()

        return 1e6 * (len(self.swapTimes)-1) / (self.swapTimes[-1] - self.swapTimes[0])

    def swapTimeAppend(self, time):
        while self.swapTimes and self.swapTimes[0] < time - self._timesWindow:
            self.swapTimes.popleft()
        self.swapTimes.append(time)
#        self.swapRateChanged.emit(self.swapRate)


    @Q.pyqtProperty(float)
    def eventRate(self):
        if len(self.eventTimes) < 2:
            return 0
        else:
            return 1e6 * (len(self.eventTimes) - 1 )/ (self.eventTimes[-1][0] - self.eventTimes[0][0])

    def eventTimeAppend(self, time, event_type=None):
        while self.eventTimes and self.eventTimes[0][0] < time - self._timesWindow:
                self.eventTimes.popleft()
        self.eventTimes.append((time,event_type))
#        self.eventRateChanged.emit(self.eventRate)


    @Q.pyqtSlot(object)
    def onEventData(self, event):
        m = self.m
        if not m:
            return
        if event.id is self.mpv.EventType.property_change:
            self.eventTimeAppend(self.m.time,'{}: {}'.format(event.id.name,event.data.name))
        else:
            self.eventTimeAppend(self.m.time,event.id.name)
        if event.id is self.mpv.EventType.shutdown:
            print("on_event -> shutdown")
#            m.set_wakeup_callback(None)
#            m.shutdown()
#            self.just_die.emit()
            return
        elif event.id is self.mpv.EventType.idle:
            self.novid.emit()
        elif event.id is self.mpv.EventType.start_file:
            self.hasvid.emit()
        elif event.id is self.mpv.EventType.audio_reconfig:
            self.af.valueChanged.emit(self.m.af)
        elif event.id is self.mpv.EventType.file_loaded:
            ao = m.ao
            print(ao)
            if ao:
                if ao[0]['name'] in ('null','none'):
                    m.aid = 0
                else:
                    m.aid = 1
            else:
                pass
            if False:
                if not m.aid:
                    if m.af:
                        self.af = m.af
                    m.af = ""
                else:
                    if self.af and not m.af:
                        m.af = self.af
            self.time_pos.forceUpdate()
            self.speed.forceUpdate()
        elif event.id is self.mpv.EventType.log_message:
            self.logMessage.emit(event.data)
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
                for rdata in event.reply_userdata:
                    try: rdata(data)
                    except: pass
            elif event.data.name == 'fullscreen':
                pass
        else:
           self.logMessage.emit('got a {} event, with data {}'.format(event.id.name,event.data))

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
            elif event.id is self.mpv.EventType.shutdown:
                return
            else:
                try:
                    self.onEventData(event)
                except Exception as e:
                    print(e)
    @Q.pyqtSlot()
    def onWakeup(self):
#        self.doWakeup.emit(self.m.time)
        self.frameTimeAppend(self.m.time)
        self.update()

    def initializeGL(self):
        print('initialize GL')

        if self._get_proc_address is 'ctypes':
            _get_proc_address = AVPlayer.get_proc_address_ctypes()
        else:
            _get_proc_address = AVPlayer.get_proc_address_qtgl()

        if self._get_proc_address_debug:
            def getprocaddr(name):
                res = _get_proc_address(name)
                print('{} -> address {}'.format(name,res))
                return res
        else:
            getprocaddr = _get_proc_address

        self.ogl = self.m.create_render_context(getprocaddr,None)
#        create_render_context(getprocaddr,None)
#        self.ogl = self.m.opengl_cb_context
        #(getprocaddr,None)
#        self.ogl.init_gl(getprocaddr,None)

        self.wakeup.connect(self.onWakeup,Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
        self.doWakeup.connect(self.frameTimeAppend,Q.Qt.QueuedConnection)
        self.frameSwapped.connect(self.onFrameSwapped,Q.Qt.DirectConnection)
        ogl = self.ogl
#        weakref.finalize(self, lambda : self.ogl.shutdown())
#        self.ogl.set_update_callback(self.wakeup.emit)
        self.destroyed.connect(lambda:(self.ogl.set_update_callback(None),self.ogl.shutdown()),Q.Qt.DirectConnection)
#        self.ogl.set_update_callback_thread(self.wakeup.emit)
        self.ogl.set_update_callback(self.onWakeup)
#        self.ogl.set_update_callback(self.wakeup.emit)
        self.openglInitialized.emit(Q.QOpenGLContext.currentContext())

    @Q.pyqtSlot()
    def onFrameSwapped(self):
        self.swapTimeAppend(self.m.time)
        if self._updated:
            self._updated = False
        if self.reportFlip:
            self.ogl.report_flip()
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

class CmdLine(Q.QLineEdit):
    submitted = Q.pyqtSignal(str,bool)
    historyPosChanged = Q.pyqtSignal(int)
    historyChanged = Q.pyqtSignal()
    historyAppended = Q.pyqtSignal(str)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history = collections.deque()
        self._history_pos = 0
        self.historyAppended.connect(self.historyChanged,Q.Qt.UniqueConnection)
        self.returnPressed.connect(self.onReturnPressed, Q.Qt.UniqueConnection)
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
    timeline_precision = 1e-5
    timeline_threshold = 1e-4
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
#                self.childwidget.setMinimumSize(Q.QSize(self.vwidth // 64,self.vheight // 64))
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
#        self.hide()

    def hasvid(self):
        self.sized_once = False
#        self.show()

    def speedChanged(self,speed):
        try:
            self.childwidget.m.speed = self.speedValueToSpeed(speed)
        except self.childwidget.mpv.MPVError as e:
            pass

    @Q.pyqtSlot(object)
    def onVideo_paramsChanged(self,params):
        try:
            self.reconfig(params['w'],params['h'])
        except:
            pass
    def speedValueToSpeed(self, val):
        if val < self.speed_base:
            return val / self.speed_base
        else:
            return self.speed_pow ** (val - self.speed_base)

    def speedToSpeedValue(self, speed):
        if speed <= 1.0:
            return int(speed * self.speed_base)
        else:
            return int(math.log(speed,self.speed_pow) + self.speed_base)


    @property
    def speedRate(self):
        return self.speedValueToSpeed(self.speed.value())

    @speedRate.setter
    def speedRate(self, value):
        self.speed.setValue(self.speedToSpeedValue(value))

    @Q.pyqtSlot(object)
    def onSpeedChanged(self,speed):
        value = self.speedToSpeedValue(speed)
        if value != self.speed.value():
            self.speed.blockSignals(True)
            self.speed.setValue(value)
            self.speed.blockSignals(False)

    def pause(self):
        self.childwidget.command("cycle","pause")

    def rate_adj(self, val):
        self.speedRate = (self.speedRate * val)

    def temp_rate(self, factor):
        self.pitch_bend *= factor
        self.speedRate = self.speedRate * factor

    @Q.pyqtSlot()
    def temp_rate_release(self):
        self.speedRate= (self.speedRate / self.pitch_bend)
        self.pitch_bend = 1.

    @property
    def timelineThreshold(self):
        if self.childwidget:
            fps = self.childwidget.container_fps.value()
            if fps:
                return max(self.timeline_threshold, 0.5 / fps)
        return self.timeline_threshold

    @Q.pyqtSlot(int)
    def onTimelineChanged(self,when):
        when *= self.timeline_precision
        cur = self.childwidget.time_pos.value()
        if cur is None or when is None:
            return
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
        self.eventTypes = defaultdict(lambda:0)
        self.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.Expanding
          , Q.QSizePolicy.Expanding
          , Q.QSizePolicy.Frame))
        childwidget = self.childwidget = AVPlayer(fp=fp,parent=None)
        childwidget.setSizePolicy(Q.QSizePolicy(
            Q.QSizePolicy.Expanding
          , Q.QSizePolicy.Expanding
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
        self.speed_max  = 5.0
        self.speed_pow  = 5.0 ** (self.speed_base**-1)
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

        toolbarlayout= Q.QVBoxLayout()
        cmdlinelayout= Q.QGridLayout()
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
        et_label = self.et_label = Q.QPlainTextEdit()
        pr_label = self.pr_label = Q.QLabel()
        fr_label = self.fr_label = Q.QLabel()
        sr_label = self.sr_label = Q.QLabel()
        self._timer = Q.QTimer(self)
        self._timer.setInterval(int(1000/8))
        self._timer.setTimerType(Q.Qt.CoarseTimer)

        def updateLabels():
            self.pr_label.setText('paint rate: {:.6f}'.format(self.childwidget.paintRate))
            self.er_label.setText('event rate: {:.6f}'.format(self.childwidget.eventRate))
            self.fr_label.setText('frame rate: {:.6f}'.format(self.childwidget.frameRate))
            self.sr_label.setText('swap rate: {:.6f}'.format(self.childwidget.swapRate))

#            if self.childwidget.eventTimes:
            _types = defaultdict(lambda :0)
#                types.clear()
            for i in range(len(self.childwidget.eventTimes)):
                _time,_type = self.childwidget.eventTimes[i]
                _types[_type] += 1

            if _types != self.eventTypes:
                self.eventTypes = _types
                self.et_label.clear()

                tc = self.et_label.textCursor()
                tc.movePosition(tc.End,tc.MoveAnchor)
#                    self.et_label.setTextCursor(tc)
                for _ in ('{}:\t{}\n'.format(_[0],_[1]) for _ in sorted(_types.items())):
                    tc.insertText(_)
#            self.histline.ensureCursorVisible()

        self._timer.timeout.connect(updateLabels,Q.Qt.QueuedConnection)
        self._timer.start()
#        self.cmdline = cmdline = CmdLine(self.toolbargroup)
        self.cmdline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        cmdlinelayout.addWidget(self.cmdline,0, 0, 1, 4)
        rate_box = cmdlinelayout

        rate_box.addWidget(er_label, 1, 0)
        rate_box.addWidget(pr_label, 1, 1)
        rate_box.addWidget(fr_label, 1, 2)
        rate_box.addWidget(sr_label, 1, 3)

#        cmdlinelayout.addLayout(rate_box)
        toolbarlayout.addLayout(cmdlinelayout)
        histloglayout.addWidget(self.histline)
        histloglayout.addWidget(self.logline )

        if use_tabs:
            tw = Q.QTabWidget(parent=None)
            tg = Q.QWidget()
            tg.setLayout(histloglayout)
            tw.addTab(tg,"history/log")
            tv = Q.QTreeView(parent=None)
#            if childwidget._property_model is not None:
            tv.setModel(childwidget._property_model)
#            childwidget.propertyModelChanged.connect(tv.setModel)
#            tv.header().setSectionResizeMode(Q.QHeaderView.Stretch)
            tw.addTab(tv,"properties")

            tw.addTab(et_label,'event types')
            toolbarlayout.addWidget(tw)
#            self._tw = tw
#            self._tv = tv
        else:
            rate_box.addWidget(et_label,2,0,1,4)
            toolbarlayout.addLayout(histloglayout)
#            self._tw = None
#            self._tv = None

        controls_layout.addLayout(toolbarlayout)
        cmdline.submitted.connect(self.onCmdlineAccept,Q.Qt.UniqueConnection|Q.Qt.AutoConnection)
        cmdline.historyChanged.connect(self.redoHistory)
        self.childwidget.logMessage.connect(self.onLogMessage)

#    def tw(self):
#        return self._tw
#        _tw = self._tw
#        if _tw is not None:
#            return _tw()

#    def tv(self):
        #_tv = self._tv
#        return _tv
#        if _tv is not None:
#            return _tv()


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
        if not isinstance(msg,(str,bytes)):
            tc.insertText('[{}]\t{}:\t{}'.format(msg.level, msg.prefix,msg.text).strip())
        else:
            tc.insertText('[internal]\t{}'.format(msg).strip())
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
    _use_tree = False
    _use_table= True

    _cw = None
    def createPlaylistDock(self):
#        from playlist import PlayList
        self.next_id = 0
#        self.playlist = PlayList(self, None)
        self.propertydock = Q.QDockWidget()
        self.propertydock.setWindowTitle("Playlist")
        self.propertydock.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
        tw = Q.QTabWidget(parent=self.propertydock)
        player = self.playerwidget
#        player._property_model = AVTreePropertyModel(player=player, parent=player)
        if self._use_tree:
            tv = Q.QTreeView()
##            if player._property_model is not None:
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
#        self.show()
#        self.raise_()
        self._timer = Q.QTimer()
#        self._timer.setInterval(int(1000/30))
        self._timer.setTimerType(Q.Qt.PreciseTimer)

        tw = Q.QTabWidget(parent=self)
        cw = CtrlPlayer(*args,parent=self, **kwargs)
#        cw.show()
        tw.addTab(cw,"video")
        tw.setVisible(True)
#        cw.childwidget.resize(self.size())
        player = cw.childwidget
#        player._property_model = AVTreePropertyModel(player=player,parent=player)
#        tv = Q.QTreeView()
#c        tv.setModel(player._property_model)
 #       tw.addTab(tv,"properties")
 #       tw.setVisible(True)
#        self.ctrlwidget = cw
        self.playerwidget = player

#        self._timer.timeout.connect(self.update)
#        self._timer.timeout.connect(cw.update)
        self._timer.timeout.connect(cw.childwidget.update)

#        self.widget = CtrlPlayer(fp=fp,parent=self)
#        self.playerwidget = self.widget.childwidget
        self.setCentralWidget(tw)

        fileMenu = self.menuBar().addMenu("&File")
#        fileMenu = self.propertydock.fileMenu
        fileMenu.addAction("&Open...",cw.openFile,"Ctrl+O")
        fileMenu.addAction("O&pen Url...",cw.openUrl,"Ctrl+Shift+O")
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
    parser.add_argument('--getprocaddress',default=None,action='store')
    parser.add_argument('--getprocaddressquiet',action='store_true')
    parser.add_argument('--times_window',default=None,type=float)
    parser.add_argument('--forcerate',type=float,default=None)
    parser.add_argument('--nrf','--no-reportflip',action='store_true')

    args = parser.parse_args()

    app = Q.QApplication([])
    media = list()
    for path in args.path:
        if '=' in path:
            pass
        else:
            media.append(path)

    mw = Canvas()
    def main(mw):
        mw.show()
        mw.raise_()

        if args.forcerate is not None and args.forcerate:
            mw.forcedFrameRate = args.forcerate
#    else:
#        mw.forcedFrameRate = None


        ap = mw.playerwidget

        if args.getprocaddress:
            ap._get_proc_address = args.getprocaddress
        if args.getprocaddressquiet:
            ap._get_proc_address_debug = False
        if args.times_window is not None:
            ap._timesWindow = args.times_window * 1e6
        def dump_fmt(fmt):
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


        ap.openglInitialized.connect(lambda x:dump_fmt(x.format()))

        if args.nrf:
            ap.reportFlip = False
        else:
            ap.reportFlip = True

#    if args.reportflip:
#        ap.reportFlip = True
        if args.extra:
            extra = args.extra.split()
            for e in extra:
                if '=' in e:
                    a,_,b = e.partition('=')
                    try:
                        ap.m.set_property(a,b)
                    except:
                        pass
        for path in args.path:
            if '=' in path:
                a,_,b = path.partition('=')
                try:
                    ap.m.set_property(a,b)
                except:
                    pass
#        else:
#            media.append(path)
        print('media: ',media)
        def load(*a):
            print('in load, {}'.format(a))
            ap.show()
            ap.resize(mw.size())
            ap.adjustSize()
            if media:
                def iload():
                    print('in iload, {}'.format(a))
                    for path in media:
                        ap.try_command('async','loadfile',path,'append-play')
                    ap.playlist_pos = 0
                    ap.playlist.valueChanged.emit(ap.m.playlist)
                Q.QTimer.singleShot(100,iload)
        Q.QTimer.singleShot(0,load)
    with SignalWakeupHandler(app):
        signal.signal(signal.SIGINT, lambda *a:app.quit())
        Q.QTimer.singleShot(1000,lambda:main(mw))
#        IPython.embed()
#        Q.QTimer.singleShot(0,IPython.embed)
        sys.exit(app.exec_())
