from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from playerwindow import PlayerWidget
from player import Player
import sys
if sys.version_info.major > 2: basestring = str

class TopWindow(Q.QMainWindow):
    def createPlaylistDock(self):
        from playlist import PlayList
        self.playlist = PlayList(self, self.players[0])
        self.playlistdock = QW.QDockWidget()
        self.playlistdock.setWindowTitle("Playlist")
        self.playlistdock.setFeatures(QW.QDockWidget.DockWidgetFloatable| QW.QDockWidget.DockWidgetMovable)
        self.playlistdock.setWidget(self.playlist)
    def onCrossfadeChanged(self, cross):
        self.players[0].m.volume = (100.- cross)/2
        print( self.players[0].m.volume)
        self.players[1].m.volume = (100 + cross )/2
        print( self.players[1].m.volume)
        print(cross)
    def openFile0(self):
        prev,self.playlist.player = self.playlist.player,self.players[0]
        self.playlist.openFile()
        self.playlist.player = prev
    def openFile1(self):
        prev,self.playlist.player = self.playlist.player,self.players[1]
        self.playlist.openFile()
        self.playlist.player = prev
    def __init__(self,n=2,*args,**kwargs):
        super(self.__class__,self).__init__()
        self.players = [Player() for _ in range(max(1,n))]
        self.createPlaylistDock()
        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.playlistdock)
        self.playlistdock.fileMenu = self.menuBar().addMenu("&File")
        self.playlistdock.fileMenu.addAction("&Open...",self.playlist.openFile,"Ctrl+O")
        self.playlistdock.fileMenu.addAction("Open player &1...",self.playlist.openFile,"Ctrl+1")
        self.playlistdock.fileMenu.addAction("Open player &2...",self.playlist.openFile,"Ctrl+2")
        self.playlistdock.fileMenu.addAction("E&xit",self.close,"Ctrl+Q")
        widget = Q.QWidget()
        layout = Q.QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        splitter = Q.QSplitter()
        layout.addWidget(splitter)
        for p in self.players:
            p.softvol=True
            splitter.addWidget(PlayerWidget(p,self,*args))
        cf = self.crossfade = Q.QSlider(Q.Qt.Horizontal)
        cf.setRange(-100,100)
        cf.setEnabled(True)
        cf.valueChanged.connect(self.onCrossfadeChanged)
        layout.addWidget(cf)

        widget.setLayout(layout)
        self.setCentralWidget(widget);

