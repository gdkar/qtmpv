from __future__ import print_function, division
from PyQt5 import QtCore, Qt, QtWidgets as QW, QtGui as QG, Qt as Q
import weakref
import sys
#from playlist import PlayList, PlayListItem
import av

class PlayerObject(Q.QOpenGLWidget):
    mpv = __import__('mpv')
    base_options = {
         'input-default-bindings':True
        ,'input_vo_keyboard':True
        ,'gapless_audio':True
        ,'osc':True
        ,'keep-open':True
        ,'load_scripts':True
        ,'ytdl':True
          }

    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
    playlistChanged = Q.pyqtSignal(object)
    playlist_posChanged = Q.pyqtSignal(int)
    time_posChanged = Q.pyqtSignal(object)
    percent_posChanged = Q.pyqtSignal(object)
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
    speedChanged = Q.pyqtSignal(object)
    durationChanged = Q.pyqtSignal(object)
    video_paramsChanged = Q.pyqtSignal(object)
    mpv_event = Q.pyqtSignal()
    mpv_frame = Q.pyqtSignal()
    jsust_die = Q.pyqtSignal()
    _widget = None
    ogl = None
    fbo = None
    evt_stats =  0
    upd_stats =  0
    frm_stats =  0

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

    @property
    def media_title(self):
        if self.m:
            try:
                return self.m.get_property('media-title')
            except self.mpv.MPVError:
                return None

    def __init__(self, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pending = []
        self.ps_cache = {}
        parent  = kwargs.pop('parent',None)

        self.playlist = list()
        self.playlist_pos = None
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        options = self.base_options
        new_options,media = self.get_options(*args ,**kwargs)
        options.update(new_options)
        options['hr-seek'] = 'yes'
#        options['gui'] = True
        options['hwdec'] = 'vaapi'
        options['vo'] = 'null'
#        options['no-video']=True
        options['opengl_hwdec_interop']='vaapi-glx'

        self.m= self.mpv.Context(**options)
        self.m.set_log_level('terminal-default')
        self.m.msg_level='all=v'
#        self.m.vo = 'opengl-cb'
        self.ogl = self.m.opengl_cb_context
        self.qctx = Q.QGLContext.currentContext()

        self.destroyed.connect(self.shutdown,Q.Qt.DirectConnection)
        self.mpv_event.connect(self.on_event,Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
        self.mpv_frame.connect(self.update,  Q.Qt.QueuedConnection|Q.Qt.UniqueConnection)
        self.m.set_wakeup_callback(self.mpv_event.emit)
        self.m.request_event(self.mpv.EventType.property_change,True)
        self.m.request_event(self.mpv.EventType.video_reconfig,True)
        self.m.request_event(self.mpv.EventType.file_loaded,True)
        self.m.request_event(self.mpv.EventType.log_message,True)

        self.m.observe_property('playlist')
        self.m.observe_property('playlist-pos')
        self.m.observe_property('percent-pos')
        self.m.observe_property('video-params')
        self.m.observe_property('duration')
        self.m.observe_property("speed")

        self.stats_timer = Q.QTimer(self)
        self.stats_timer.start(1000)
        self.stats_timer.timeout.connect(self.statsTimeout)
        for option in options.items():
            for fn in (self.m.set_option,self.m.set_property):
                try:
                    fn(*option)
                    break
                except self.mpv.MPVError as e:
                    print(e,*option)
        self.show()
        self.update()
        for med in media:
            print(med)
            self.pending.append(med)
#            self.m.command('loadfile',med,'append')
#        if media:   self.m.playlist_pos =0

    @Q.pyqtSlot()
    def statsTimeout(self):
        evt,upd,frm,self.evt_stats,self.upd_stats,self.frm_stats = (
            self.evt_stats,self.upd_stats,self.frm_stats,0,0,0)

        print('evt_stats: ',evt,'upd_stats: ',upd,'frm_stats: ',frm)
    def command(self,*args):
        self.m.command(*args)

    def try_command(self, *args):
        try: self.m.command(*args)
        except self.mpv.MPVError: pass

    def setProperty(self,prop,*args):
        try:
            self.m.set_property(prop,*args)
        except:
            super().setProperty(prop,*args)

    @Q.pyqtSlot()
    def shutdown(self):
        if self.ogl:
            self.ogl.shutdown()
            self.ogl = None
        if self.m:
            self.m.shutdown()

    @Q.pyqtSlot()
    def on_event(self):
        m = self.m
        if not m:
            return
        for evt in range(16):
            event = m.wait_event(0)
            if event is None:
                print("Warning, received a null event.")
            elif event.id is self.mpv.EventType.none:
                break
#            break
            else:
                self.evt_stats += 1
                if event.id is self.mpv.EventType.shutdown:
                    print("on_event -> shutdown")
                    self.just_die.emit()
                    return
                elif event.id is self.mpv.EventType.idle:          self.novid.emit()
                elif event.id is self.mpv.EventType.start_file:    self.hasvid.emit()
                elif event.id is self.mpv.EventType.log_message:   print(event.data.text,)
                elif (event.id is self.mpv.EventType.end_file
                        or event.id is self.mpv.EventType.video_reconfig):
                    try:
                        self.reconfig.emit(self.m.dwidth, self.m.dheight)
                    except self.mpv.MPVError as ex:
                        pass
                elif event.id is self.mpv.EventType.property_change:
                    name = event.data.name.replace('-','_')
                    data  = event.data.data
                    cached = self.ps_cache.get(name,None)
                    if cached is not None:
                        cached(data)
                    else:
                        trial = name+'Changed'
                        prop_changed = getattr(self,trial,None)
                        if prop_changed and (hasattr(prop_changed,'emit')):
                            self.ps_cache[name]= prop_changed.emit
                            prop_changed.emit(data)
                        elif prop_changed and callable(prop_changed):
                            self.ps_cache[name]= prop_changed
                            prop_changed(data)
#                    elif oname == 'fullscreen':
#                        pass
#        self.mpv_event.emit()
    def initializeGL(self):
        print('initialize GL')
        pfl = Q.QOpenGLVersionProfile()
        pfl.setVersion(4,1)
        pfl.setProfile(Q.QSurfaceFormat.CoreProfile)
        self.vfuncs = self.context().versionFunctions(pfl)
        self.ctx = self.context()
        self.m.vo = 'opengl-cb'
        self.ogl = self.m.opengl_cb_context
        self.qctx = Q.QGLContext.currentContext()
        def getprocaddr(name):
            print(name)
            fn = self.qctx.getProcAddress(name.decode('latin1'))
            return fn
        self.ogl.init_gl(getprocaddr,None)
#        self.ogl.set_update_callback(self.mpv_frame.emit)
        def record_upd():self.upd_stats += 1
        self.mpv_frame.connect(record_upd)
        self.frameSwapped.connect(lambda:self.ogl.report_flip(self.m.time))
        def record_frm():self.frm_stats += 1
        self.frameSwapped.connect(record_frm)

#        self.mpv_frame.emit)
        if self.pending:
            for med in self.pending:
                self.m.command('loadfile',med,'append')
            self.m.playlist_pos = 0
#        if media:   self.m.playlist_pos =0

    def paintGL(self):
        self.ogl.draw(self.defaultFramebufferObject(),self.width,-self.height)

    def resizeGL(self, w, h):
        print(('resize to', w, h))
        self.width  = w
        self.height = h

    @property
    def widget(self):
        return self._widget() if self._widget is not None else None

    @widget.setter
    def widget(self, _widget):
        self._widget = weakref.ref(_widget) if _widget else None

