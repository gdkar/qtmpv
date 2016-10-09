from __future__ import division
#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from functools import partial,partialmethod
import sys
if sys.version_info.major > 2:
    basestring = str
class PlayerWidget(Q.QWidget):
    requestFile = Q.pyqtSignal(object)
    def novid(self):
        self.hide()
    def hasvid(self):
        self.show()
    def reconfig(self,width,height):
        self.wwidth = width
        self.wheight= height
        if not self.sized_once and width:
            self.resize(self.sizeHint())
            self.sized_once = True
    def sizeHint(self):
        if not self.vwidth:
            return QW.QWidget.sizeHint(self)
        return Q.QSize(self.vwidth, self.vheight)
    @Q.pyqtSlot(int)
    def onTimelineChanged(self,when):
        self.player.command("seek",when*100./self.timeline_base,"absolute-percent")
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
    def rate_forward(self):
        self.speed.setValue(int(self.speed.value() * 1.1))
    def rate_back(self):
        self.speed.setValue(int(self.speed.value() / 1.1))
    def temp_rate(self, factor):
        self.pitch_bend *= factor
        self.speed.setValue(int(self.speed.value() * factor))
    @Q.pyqtSlot()
    def temp_rate_forward(self): self.temp_rate(1.1)
    @Q.pyqtSlot()
    def temp_rate_back(self):    self.temp_rate(1./1.1)
    @Q.pyqtSlot()
    def temp_rate_release(self):
        self.speed.setValue(int(self.speed.value() / self.pitch_bend))
        self.pitch_bend = 1.
    @Q.pyqtSlot(object)
    def onRequestFile(self, path):
        print("Setting playlist binding to ", self)
        self.playlist.setPlayer(self.player)
        self.playlist.onRequestFile(path)
    def mousePressEvent(self,event):
        print("Setting playlist binding to ", self)
        self.playlist.setPlayer(self.player)
        super(self.__class__,self).mousePressEvent(event)
    def __init__(self,player,parent, *args, **kwargs):
        super(self.__class__,self).__init__(parent)
        self.pitch_bend = 1.0
        self.player = player
        self.parent = parent
        self.vwidth = None
        self.vheight = None
        self.childwin = Q.QWindow()
        self.childwidget = Q.QWidget.createWindowContainer(self.childwin)
        self.layout = Q.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.childwidget)
        self.setLayout(self.layout)

        self.rate = None
        self.timeline = Q.QSlider(Q.Qt.Horizontal)
        self.timeline_base = 1e9
        self.timeline.valueChanged.connect(self.onTimelineChanged)
        self.speed      = Q.QSlider(Q.Qt.Horizontal)
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
        rate_down_button.clicked.connect(self.rate_back)

        rate_down_tmp_button = Q.QPushButton(" tmp -")
        rate_down_tmp_button.pressed.connect(self.temp_rate_back)
        rate_down_tmp_button.released.connect(self.temp_rate_release)

        rate_up_button = Q.QPushButton("rate +")
        rate_up_button.clicked.connect(self.rate_forward)

        rate_up_tmp_button = Q.QPushButton(" tmp +")
        rate_up_tmp_button.pressed.connect(self.temp_rate_forward)
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
        player.novid.connect(self.novid)
        self.sized_once = False
        player.hasvid.connect(self.hasvid)
#        self.layout.addWidget(self.videocontainer)
        self.layout.addLayout(control_layout)
        self.layout.addWidget(self.timeline)
        self.playlist = self.parent.playlist
        self.requestFile.connect(self.onRequestFile)
#        self.player.playlist_poschanged.connect(self.playlist.onplaylist_poschanged)
        self.player.init(int(self.childwin.winId()),*args,**kwargs)
