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
    def crossfadechanged(self, cross):
        self.players[0].volume = (100.- cross)/2
        print( self.players[0].volume)
        self.players[1].volume = (100 + cross )/2
        print( self.players[1].volume)
        print(cross)
    def __init__(self,n=2,*args,**kwargs):
        super(self.__class__,self).__init__()
        self.players = []
        self.players.append(Player())
        self.players.append(Player())
        self.createPlaylistDock()
        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.playlistdock)
        self.playlistdock.fileMenu = self.menuBar().addMenu("&File")
        self.playlistdock.fileMenu.addAction("&Open...",self.playlist.openFile,"Ctrl+O")
        self.playlistdock.fileMenu.addAction("E&xit",self.close,"Ctrl+Q")
        #for i in range(n):
#            self.players.append(player)
        widget = Q.QWidget()
        layout = Q.QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        splitter = Q.QSplitter()
        layout.addWidget(splitter)
        for player in self.players:
            player.softvol=True
            playerwidget = PlayerWidget(player,self,*args)
            splitter.addWidget(playerwidget)
        self.crossfade = Q.QSlider(Q.Qt.Horizontal)
        crossfade = self.crossfade
        crossfade.setRange(-100,100)
        crossfade.setEnabled(True)
        crossfade.valueChanged.connect(self.crossfadechanged)
        layout.addWidget(crossfade)
        widget.setLayout(layout)
        self.setCentralWidget(widget);

