from __future__ import division
#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from functools import partial,partialmethod
import sys

class PlayerWidget(Q.QWidget):
    requestFile = Q.pyqtSignal(object)
    def novid(self):
        self.sized_once = False
        self.hide()
    def hasvid(self):
        self.sized_once = False
        self.show()
    def idealConfig(self):
        try:
            params = self.player.video_params
            if params['w'] and params['h']:
                self.vwidth = params['w']
                self.vheight = params['h']
                self.childwidget.setMinimumSize(Q.QSize(self.vwidth,self.vheight))
                self.sized_once = True
                self.show()
                self.adjustSize()
                self.window().update()
        except:
            self.sized_once = False
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
            self.parent().adjustSize()
            self.window().update()
            if not self.sized_once:
                self.sized_once = True
                self.show()
    def closeEvent(self,evt):
#        self.player.shutdown()
        self.player.setParent(self)
        self.novid()

    @Q.pyqtSlot(int)
    def onCrossfadeChanged(self, val):
        if self.player.index %2:
            self.player.m.volume = (100 - val) / 2
        else:
            self.player.m.volume = (100 + val)/2

#    def sizeHint(self):
#        if not self.vwidth or not self.vheight:
#            return super().sizeHint()
#        return Q.QSize(self.vwidth, self.vheight)
    @Q.pyqtSlot(object)
    def onVideo_paramsChanged(self,params):
#        print("video params changed: ",repr(params))
        try:
            self.reconfig(params['w'],params['h'])
        except:
            pass
    @Q.pyqtSlot(int)
    def onTimelineChanged(self,when):
        s = min(max(0.,when * 100./self.timeline_base),100.)
        self.player.try_command("seek",s,"absolute-percent")

    @Q.pyqtSlot(object)
    def onPercent_posChanged(self,percent_pos):
        if percent_pos:
            self.timeline.blockSignals(True)
            self.timeline.setValue(percent_pos * self.timeline_base/100)
            self.timeline.blockSignals(False)
    def speedChanged(self,speed):
        try:
            self.player.m.speed = speed * 1.0/self.speed_base
        except self.player.mpv.MPVError as e:
            pass
    @Q.pyqtSlot(object)
    def onSpeedChanged(self,speed):
        if speed * self.speed_base != self.speed.value():
            self.speed.blockSignals(True)
            self.speed.setValue(int(speed * self.speed_base))
            self.speed.blockSignals(False)
    def pause(self):
        self.player.command("cycle","pause")
    def rate_adj(self, val):
        self.speed.setValue(int(self.speed.value() * val))
    def temp_rate(self, factor):
        self.pitch_bend *= factor
        self.speed.setValue(int(self.speed.value() * factor))

    @Q.pyqtSlot()
    def temp_rate_release(self):
        self.speed.setValue(int(self.speed.value() / self.pitch_bend))
        self.pitch_bend = 1.
    @Q.pyqtSlot(object)
    def onRequestFile(self, path):
#        print("Setting playlist binding to ", self)
        self.playlist.setPlayer(self.player)
        self.playlist.onRequestFile(path)

    def mousePressEvent(self,event):
#        print("Setting playlist binding to ", self)
        self.playlist.setPlayer(self.player)
        super().mousePressEvent(event)
    def __init__(self,player,parent, *args, **kwargs):
        super().__init__(parent)
        self.setAttribute(Q.Qt.WA_DeleteOnClose)
        policy = Q.QSizePolicy(Q.QSizePolicy.MinimumExpanding,Q.QSizePolicy.MinimumExpanding,Q.QSizePolicy.Frame)
        self.setSizePolicy(policy)
        self.pitch_bend = 1.0
        self.player = player
        self._parent = parent
        self.vwidth = None
        self.vheight = None
        self.childwin = Q.QWindow()
        self.childwidget = Q.QWidget.createWindowContainer(self.childwin)
        policy = Q.QSizePolicy(Q.QSizePolicy.MinimumExpanding,Q.QSizePolicy.MinimumExpanding,Q.QSizePolicy.Label)
#        policy.setRetainSizeWhenHidden(True)
        self.childwidget.setSizePolicy(policy)
        self.layout = Q.QVBoxLayout()
#        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.childwidget)
        self.setLayout(self.layout)

        self.rate = None
        self.timeline = Q.QSlider(Q.Qt.Horizontal)
        self.timeline.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.timeline_base = 1e9
        self.timeline.valueChanged.connect(self.onTimelineChanged)
        self.speed      = Q.QSlider(Q.Qt.Horizontal)
        self.speed.setSizePolicy(Q.QSizePolicy.Expanding,Q.QSizePolicy.Preferred)
        self.speed_base = 1e9
        self.speed.setValue(self.speed_base)
        self.speed.setRange(16,2*self.speed_base)
        self.speed.setEnabled(True)
        self.speed.valueChanged.connect(self.speedChanged)
        self.player.speedChanged.connect(self.onSpeedChanged)
        self.player.percent_posChanged.connect(self.onPercent_posChanged)
        self.timeline.setRange(0,self.timeline_base)
        self.timeline.setEnabled(True)

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

        player.reconfig.connect(self.reconfig)
        player.video_paramsChanged.connect(self.onVideo_paramsChanged)
        player.novid.connect(self.novid)
        self.sized_once = False
        player.hasvid.connect(self.hasvid)
#        self.layout.addWidget(self.videocontainer)
        self.layout.addLayout(control_layout)
        self.layout.addWidget(self.timeline)
        self.playlist = self._parent.playlist
        self.requestFile.connect(self.onRequestFile)
#        self.player.playlist_poschanged.connect(self.playlist.onplaylist_poschanged)
        self.player.init(self,*args,**kwargs)
