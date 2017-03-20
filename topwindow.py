from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from playerwidget import PlayerWidget
from player import Player
import sys
class TopWindow(Q.QMainWindow):
    crossfadeChanged = Q.pyqtSignal(int)
    def createPlaylistDock(self):
        from playlist import PlayList
        self.next_id = 0
        self.playlist = PlayList(self, None)
        self.playlistdock = QW.QDockWidget()
        self.playlistdock.setWindowTitle("Playlist")
        self.playlistdock.setFeatures(QW.QDockWidget.DockWidgetFloatable| QW.QDockWidget.DockWidgetMovable)
        self.playlistdock.setWidget(self.playlist)
    def onCrossfadeChanged(self, cross):
        pass
#        self.players[0].m.volume = (100.- cross)/2
#        print( self.players[0].m.volume)
#        self.players[1].m.volume = (100 + cross )/2
#        print( self.players[1].m.volume)
#        print(cross)
    def getPlayerAt(self, where = -1):
        player = None
        if where >= 0:
            for p in self.players:
                if p.index == where:
                    player = p
                    if p.widget and p.m:
                        return p
                    break
        if player is None:
            for p in self.players:
                if not p.widget or p.index < 0:
                    player = p
                    player.index = self.next_id
                    self.next_id+=1
                    break
        if player is None:
            player = Player(parent=self)
            player.index = self.next_id
            self.next_id += 1

            self.shutdown.connect(player.shutdown,Q.Qt.DirectConnection)
#            self.players.append(player)

        if not player.widget:
            self.makeWidgetFor(player)

        self.playlist.updateActions()

        return player
    shutdown = Q.pyqtSignal()
    def openFile(self, where = -1 ):
        prev = self.playlist.player
        player = self.getPlayerAt(where)

        self.playlist.player = player
        self.playlist.openFile()
        self.playlist.player = prev

    def openUrl(self, where = -1 ):
        prev = self.playlist.player
        player = self.getPlayerAt(where)

        self.playlist.player = player
        self.playlist.openUrl()
        self.playlist.player = prev

    cascadeSubWindows = Q.pyqtSignal()
    @property
    def players(self):
        return self.findChildren(Player)

    childChanged = Q.pyqtSignal(object)

    def childEvent(self,evt):
        self.childChanged.emit(evt)

    def __init__(self,*args,**kwargs):
        super().__init__()
        self.setAttribute(Q.Qt.WA_DeleteOnClose)
#        self.players = list()
#        self.players = [Player() for _ in range(max(1,n))]
        mdiArea = Q.QMdiArea(self)
        self.mdiArea = mdiArea
        self.setCentralWidget(mdiArea)

        self.createPlaylistDock()
        self.addDockWidget(Q.Qt.LeftDockWidgetArea,self.playlistdock)

        self.playlistdock.fileMenu = self.menuBar().addMenu("&File")
        fileMenu = self.playlistdock.fileMenu
        fileMenu.addAction("&Open...",lambda:self.openFile(-1),"Ctrl+O")
        fileMenu.addAction("Open &Url...",lambda:self.openUrl(-1),"Ctrl_U")
        fileMenu.addAction("E&xit",self.close,"Ctrl+Q")

        self.childChanged.connect(self.playlist.updateActions)

        cf_bar = self.addToolBar("Crossfade")
        cf_bar.setFloatable(True)
        cf_bar.setMovable(True)
        cf = self.crossfade = Q.QSlider(Q.Qt.Horizontal)
        cf.setRange(-100,100)
        cf.setEnabled(True)
        cf.valueChanged.connect(self.crossfadeChanged)
        self.crossfadeChanged.connect(self.onCrossfadeChanged)
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
        mdiArea.subWindowActivated.connect(lambda *x: self.playlist.setPlayer(mdiArea.activeSubWindow()))
        self.destroyed.connect(self.shutdown,Q.Qt.DirectConnection)
        self._options,media = Player.get_options(*args)
#        if media:
#            for item in media:
#                self.getPlayer(0).getPlayer
        if media:
            p = self.getPlayerAt(-1)
            self.playlist.player = p
            self.playlist.updateActions()
#            self.makeWidgetFor(p,*args,**kwargs)
            list(map(self.playlist.onRequestFile,media))

    def makeWidgetFor(self,player,*args, **kwargs):
        if player:
            player.softvol = True
            for option in self._options.items():
                player.m.set_option(*option)
            pw = PlayerWidget(player,self,*args, **kwargs)
            pw.childwin.resize(self.size())
            self.cascadeSubWindows.connect(pw.idealConfig)
            self.crossfadeChanged.connect(pw.onCrossfadeChanged)
            self.mdiArea.addSubWindow(pw)
            pw.adjustSize()
            pw.parent().adjustSize()
            pw.parent().update()
            pw.destroyed.connect(pw.parent().close,Q.Qt.DirectConnection)
#            pw.setVisible(True)
            return pw
