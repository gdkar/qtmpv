from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from playerwidget import PlayerWidget
from player import Player
import sys
class TopWindow(Q.QMainWindow):
    def createPlaylistDock(self):
        from playlist import PlayList
        self.playlist = PlayList(self, None)
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
    def getPlayerAt(self, where = -1):
        if where >= 0 and where < len(self.players):
            player = self.players[where]
        else:
            player = Player(parent=self)
            self.shutdown.connect(player.shutdown)
            self.players.append(player)
            self.playlist.updateActions()

        w = player.widget
        if not w:
            self.makeWidgetFor(player)
        return player
    shutdown = Q.pyqtSignal()
    def openFile(self, where = -1 ):
        prev = self.playlist.player
        player = self.getPlayerAt(where)

        self.playlist.player = player
        self.playlist.openFile()
        self.playlist.player = prev

    cascadeSubWindows = Q.pyqtSignal()
    def __init__(self,n=2,*args,**kwargs):
        super().__init__()
        self.players = list()
#        self.players = [Player() for _ in range(max(1,n))]
        mdiArea = Q.QMdiArea(self)
        self.mdiArea = mdiArea
        self.setCentralWidget(mdiArea)

        self.createPlaylistDock()
        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.playlistdock)

        self.playlistdock.fileMenu = self.menuBar().addMenu("&File")
        fileMenu = self.playlistdock.fileMenu
        fileMenu.addAction("&Open...",lambda:self.openFile(-1),"Ctrl+O")
        fileMenu.addAction("E&xit",self.close,"Ctrl+Q")


        cf_bar = self.addToolBar("Crossfade")
        cf_bar.setFloatable(True)
        cf_bar.setMovable(True)
        cf = self.crossfade = Q.QSlider(Q.Qt.Horizontal)
        cf.setRange(-100,100)
        cf.setEnabled(True)
        cf.valueChanged.connect(self.onCrossfadeChanged)
        cf_bar.addWidget(cf)

        cf_bar = self.addToolBar(Q.Qt.BottomToolBarArea,cf_bar)

        self.winMenu = self.menuBar().addMenu("&Window")
        winMenu = self.winMenu
        winMenu.addAction("Cl&ose",mdiArea.closeActiveSubWindow)
        winMenu.addAction("Close&All",mdiArea.closeAllSubWindows)
        winMenu.addAction("&Tile",mdiArea.tileSubWindows)
        cascadeAction = winMenu.addAction("&Cascade",self.cascadeSubWindows)
        cascadeAction.triggered.connect(mdiArea.cascadeSubWindows)
        winMenu.addAction("Ne&xt",mdiArea.activateNextSubWindow,Q.QKeySequence.NextChild)
        winMenu.addAction("&Prev",mdiArea.activatePreviousSubWindow,Q.QKeySequence.PreviousChild)
        if args:
            p = Player(parent=self)
            self.shutdown.connect(p.shutdown)
            self.players.append(p)
            self.playlist.updateActions()
            self.makeWidgetFor(self.players[-1],*args)
#        for p in self.players:
#            self.makeWidgetFor(p,*args)
#            splitter.addWidget(PlayerWidget(p,self,*args))

    def makeWidgetFor(self,player,*args):
        if player:
            player.softvol = True
            pw = PlayerWidget(player,self,*args)
            pw.childwin.resize(self.size())
            self.cascadeSubWindows.connect(pw.idealConfig)
            self.mdiArea.addSubWindow(pw)
            pw.adjustSize()
            pw.parent().adjustSize()
            pw.parent().update()
#            pw.setVisible(True)
            return pw
