from __future__ import print_function, division
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
import weakref
import sys
from playlist import PlayList, PlayListItem
import mpv

class Player(Q.QObject):
    mpv = __import__('mpv')
    novid = Q.pyqtSignal()
    hasvid = Q.pyqtSignal()
    playlistChanged = Q.pyqtSignal(object)
    playlist_posChanged = Q.pyqtSignal(int)
    percent_posChanged = Q.pyqtSignal(object)
    reconfig = Q.pyqtSignal(int,int)
    fullscreen = Q.pyqtSignal(bool)
    speedChanged = Q.pyqtSignal(object)
    video_paramsChanged = Q.pyqtSignal(object)
    wakeup = Q.pyqtSignal()
    def get_options(self,*args,**kwargs):
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
        try:
            return self.m.get_property('media-title')
        except self.mpv.MPVError as e:
            return None
    def remove_m(self):
        if self.m:
            self.m.set_wakeup_callback(None)
            self.m.shutdown()
            del self.m
            self.m = None
    def shutdown(self):
        self.remove_m()
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        kwargs.pop('parent',None)
        self.playlist = list()
        self.playlist_pos = None
        self._widget = None
        self.wakeup.connect(self.on_event)
        options,media = self.get_options(*args,**kwargs)
        import locale
        locale.setlocale(locale.LC_NUMERIC,'C')
        try:
            self.m = self.mpv.Context('osc','input_default_bindings',**options)
        except self.mpv.MPVError as ex:
            print("Failed creating context",ex)
            Q.qApp.exit(1)
            raise ex

        self.destroyed.connect(self.remove_m)
        self.m.set_wakeup_callback(self.wakeup.emit)
        self.m.request_event(self.mpv.Events.property_change,True)
        self.m.request_event(self.mpv.Events.video_reconfig,True)
#        self.m.request_event(self.mpv.Events.file_loaded,True)
        self.m.request_event(self.mpv.Events.log_message,True)

        self.m.observe_property('playlist')
        self.m.observe_property('playlist-pos')
        self.m.observe_property('percent-pos')
        self.m.observe_property('fullscreen')
        self.m.observe_property('video-params')
        self.m.observe_property("speed")
    @property
    def widget(self):
        return self._widget() if self._widget is not None else None

    def init(self,widget,*args,**kwargs):
        pwidget = self.widget
        if pwidget:
            return
        options,media = self.get_options(*args,**kwargs)
        self._widget = weakref.ref(widget)
        if not self.m:
            try:
                self.m = self.mpv.Context('osc','input_default_bindings',**options)
            except self.mpv.MPVError as ex:
                print("Failed creating context",ex)
                Q.qApp.exit(1)
                raise ex
        wid = int(widget.childwin.winId())
        print("attempting to use window id ",wid)
        self.m.set_option('wid',wid)
        for option in options.items():
            self.m.set_option(*option)
        self.m.set_wakeup_callback(self.wakeup.emit)
#        self.m.request_event(self.mpv.Events.property_change,True)
#        self.m.request_event(self.mpv.Events.video_reconfig,True)
#        self.m.request_event(self.mpv.Events.file_loaded,True)
#        self.m.request_event(self.mpv.Events.log_message,True)
        self.m.observe_property('playlist')
        self.m.observe_property('playlist-pos')
        self.m.observe_property('percent-pos')
        self.m.observe_property('fullscreen')
        self.m.observe_property('video-params')
        self.m.observe_property("speed")

        for med in media:
            print(med)
            self.m.command('loadfile',med,'append')

        if media:
            self.m.playlist_pos =0
        try:
            self.m.vid = 1
        except:
            pass

        return self
    def command(self,*args):
        self.m.command(*args)
    def try_command(self, *args):
        try:
            self.m.command(*args)
        except self.mpv.MPVError as e:
            pass
    def set_property(self,prop,*args):
        self.m.set_property(prop,*args)
    @Q.pyqtSlot()
    def on_event(self):
        while True:
            event = self.m.wait_event(0)
            if event is None:
                print("Warning, received a null event.")
                continue;

            if event.id == self.mpv.Events.none:
                break;
            elif event.id == self.mpv.Events.shutdown:
#                Q.qApp.exit()
                break;
            elif event.id == self.mpv.Events.idle:
                self.novid.emit()
            elif event.id == self.mpv.Events.start_file:
                self.hasvid.emit()
            elif event.id == self.mpv.Events.log_message:
                print(event.data.text,)
            elif (event.id == self.mpv.Events.end_file
                    or event.id == self.mpv.Events.video_reconfig):
                try:
                    self.m.vid = 1
                    self.reconfig.emit(
                        self.m.dwidth,
                        self.m.dheight
                    )
                except self.mpv.MPVError as ex:
                    self.reconfig.emit(None,None)
            elif event.id == self.mpv.Events.property_change:
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
