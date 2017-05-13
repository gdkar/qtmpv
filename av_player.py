
try:
    basestring
except NameError:
    basestring = str

import argparse
import ctypes
import struct, array
import os
import sys
import pprint
import time

from qtproxy import Q

import av
import mpv


class PlayerGLWidget(Q.OpenGLWidget):
    base_options = {
         'input-default-bindings':True
        ,'input_vo_keyboard':True
        ,'gapless_audio':True
        ,'osc':True
        ,'keep-open':False
        ,'load_scripts':False
        ,'ytdl':True
          }

    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
    playlistChanged = Q.pyqtSignal(object)
    playlist_posChanged = Q.pyqtSignal(int)
    time_posChanged = Q.pyqtSignal(object)
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
    speedChanged = Q.pyqtSignal(object)
    durationChanged = Q.pyqtSignal(object)
    video_paramsChanged = Q.pyqtSignal(object)
    wakeup = Q.pyqtSignal()
    mpv_event = Q.pyqtSignal()
    just_die = Q.pyqtSignal()
    mpv = __import__('mpv')
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

    def __init__(self, fp, *args, **kwargs):
        super().__init__(*args,**kwargs)
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        options = self.base_options
        new_options,media = self.get_options(*args ,**kwargs)
        options.update(new_options)
        options['hr-seek'] = 'yes'
        options['hwdec'] = 'vaapi'
        options['hwdec-preload'] = True
        options['vo'] = 'opengl-cb'
        options['opengl_hwdec_interop']='vaapi-glx'

        self.m= self.mpv.Context(**options)

        self.m.set_log_level('terminal-default')
        self.mpv_event.connect(self.onEvent,Q.QueuedConnection|Q.UniqueConnection)
        self.m.set_wakeup_callback(self.mpv_event.emit)
        self.m.request_event(self.mpv.Events.property_change,True)
        self.m.request_event(self.mpv.Events.video_reconfig,True)
        self.m.request_event(self.mpv.Events.file_loaded,True)
        self.m.request_event(self.mpv.Events.log_message,True)

        self.m.observe_property('playlist')
        self.m.observe_property('playlist-pos')
        self.m.observe_property('time-pos')
        self.m.observe_property('video-params')
        self.m.observe_property('duration')
        self.m.observe_property("speed")

        self.img_width      = 1366;#self.mpv.width
        self.img_height     = 768;#self.mpv.height
        self.img_update     = None
        self.setMinimumSize(self.img_width,self.img_height)
        self.width = self.img_width
        self.tex_id = 0
        self.height = self.img_height
        self.wakeup.connect(self.onWakeup,Q.QueuedConnection|Q.UniqueConnection)

        self.m.command('loadfile',fp,'append-play')

    @Q.pyqtSlot()
    def onEvent(self):
        m = self.m
        if not m:
            return
        while True:
            event = m.wait_event(0)
            if event is None:
                print("Warning, received a null event.")
            elif event.id is self.mpv.Events.none:
                break
#                pass
            else:
                if event.id is self.mpv.Events.shutdown:
                    print("on_event -> shutdown")
                    self.just_die.emit()
                elif event.id is self.mpv.Events.idle:          self.novid.emit()
                elif event.id is self.mpv.Events.start_file:    self.hasvid.emit()
#                elif event.id is self.mpv.Events.file_loaded:   self.durationChanged.emit(m.duration)
                elif event.id is self.mpv.Events.log_message:   print(event.data.text,)
                elif (event.id is self.mpv.Events.end_file
                        or event.id is self.mpv.Events.video_reconfig):
                    try:
                        self.m.vid = 1
                        self.reconfig.emit( self.m.dwidth, -self.m.dheight )
                    except self.mpv.MPVError as ex:
                        self.reconfig.emit(None,None)
                elif event.id is self.mpv.Events.property_change:
                    name = event.data.name.replace('-','_')
                    if hasattr(self,name+'Changed'):
                        prop_changed = getattr(self,name+'Changed')
                        if(hasattr(prop_changed,'emit')):
                            setattr(self,name,event.data.data)
                            prop_changed.emit(event.data.data)
                        elif callable(prop_changed):
                            prop_changed(event.data.data)
                    elif event.data.name == 'fullscreen':
                        pass
    @Q.pyqtSlot()
    def onWakeup(self):
        self.update()

    def initializeGL(self):
        print('initialize GL')
        pfl = Q.OpenGLVersionProfile()
        pfl.setVersion(4,1)
        pfl.setProfile(Q.SurfaceFormat.CoreProfile)
        self.vfuncs = Q.OpenGLContext.currentContext().versionFunctions(pfl)
        self.ogl = self.m.opengl_cb_context
        self.qctx = Q.GLContext.currentContext()
        def getprocaddr(name):
            print(name)
            fn = self.qctx.getProcAddress(name.decode('latin1'))
            return fn
        self.ogl.init_gl(getprocaddr,None)
        self.ogl.set_update_callback(self.wakeup.emit)
        self.frameSwapped.connect(lambda:self.ogl.report_flip(self.m.time))
    def resizeGL(self, w, h):
        print(('resize to', w, h))
        self.width  = w
        self.height = h

    def paintGL(self):
        img_update, self.img_update = self.img_update, False
        self.ogl.draw(self.defaultFramebufferObject(),self.width,-self.height)
        return

class Canvas(Q.MainWindow):
    def __init__(self,filename,format=None,parent=None):
        super(self.__class__,self).__init__(parent)
        self.widget = PlayerGLWidget(fp=filename)
        self.setCentralWidget(self.widget)


parser = argparse.ArgumentParser()
parser.add_argument('-f', '--format')
parser.add_argument('path')
args = parser.parse_args()
fmt = Q.SurfaceFormat.defaultFormat()
fmt.setVersion(4,5)
fmt.setProfile(Q.SurfaceFormat.CoreProfile)
fmt.setSamples(4)
Q.SurfaceFormat.setDefaultFormat(fmt)

app = Q.Application([])

glcanvas = Canvas(args.path,format=args.format)
glcanvas.show()
glcanvas.raise_()

app.exec_()
