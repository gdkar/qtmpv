from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
#from playerwidget import PlayerWidget
from av_player import AVPlayer, CtrlPlayer
from av_propertymodel import AVTreePropertyModel
import traceback
import sys
class TopWindow(Q.QMainWindow):
    crossfadeChanged = Q.pyqtSignal(int)
    shutdown = Q.pyqtSignal()
    cascadeSubWindows = Q.pyqtSignal()
    childChanged = Q.pyqtSignal(object)
    _use_tabs = False
    _use_mdi  = False

    def createPlaylistDock(self):
        from playlist import PlayList
        self.next_id = 0
        self.playlist = PlayList(self, None)
        self.playlistdock = QW.QDockWidget()
        self.playlistdock.setWindowTitle("Playlist")
        self.playlistdock.setFeatures(QW.QDockWidget.DockWidgetFloatable| QW.QDockWidget.DockWidgetMovable)

        self.playlistsplit = QW.QSplitter()
        self.playlistsplit.setOrientation(Q.Qt.Vertical)
        self.playlistsplit.addWidget(self.playlist)
#        tv = self.dockprops = Q.QTreeView()
#        self.playlistsplit.addWidget(tv)
        self.playlistdock.setWidget(self.playlistsplit)
#        self.playlist.playerChanged.connect(self.setDockModel)

#        from playlist import PlayList
#        self.playlist = PlayList(self, None)
#        self.propertydock = Q.QDockWidget()
#        self.propertydock.setWindowTitle("Properties")
#        self.propertydock.setFeatures(Q.QDockWidget.DockWidgetFloatable| Q.QDockWidget.DockWidgetMovable)
#        self.propertyview = Q.QTableView(self.propertydock)
#        self.propertymodel= None
##        self.propertyview.setModel(self.propertymodel)
#        def set_propertymodel(player):
#            if player and player._property_model:
#                self.propertyview.setModel(player._property_model)
#        self.playlist.playerChanged.connect(set_propertymodel)
#        self.propertydock.setWidget(self.propertyview)
#        self.propertydock.show()
#        self.playlistdock.setWidget(self.playlist)

#    def setDockModel(self, player):
#        if player:
#            self.dockprops.setModel(player._property_model)
#        else:
#            self.dockprops.setModel(None)

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
                    return p
        if player is None:
            player = self.makeWidgetFor()

        self.playlist.updateActions()

        return player
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

    @property
    def players(self):
        return self.findChildren(AVPlayer)

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
#        self.addDockWidget(Q.Qt.BottomDockWidgetArea,self.propertydock)

        self.playlistdock.fileMenu = self.menuBar().addMenu("&File")
        fileMenu = self.playlistdock.fileMenu
        fileMenu.addAction("&Open...",lambda:self.openFile(-1),"Ctrl+O")
        fileMenu.addAction("Open &Url...",lambda:self.openUrl(-1),"Ctrl_U")
        fileMenu.addAction("E&xit",self.close,"Ctrl+Q")

        self.childChanged.connect(self.playlist.updateActions,Q.Qt.DirectConnection)

        cf_bar = self.addToolBar("Crossfade")
        cf_bar.setFloatable(True)
        cf_bar.setMovable(True)
        cf = self.crossfade = Q.QSlider(Q.Qt.Horizontal)
        cf.setRange(-100,100)
        cf.setEnabled(True)
#        cf.valueChanged.connect(self.crossfadeChanged)
#        self.crossfadeChanged.connect(self.onCrossfadeChanged)
        cf_bar.addWidget(cf)

        cf_bar = self.addToolBar(Q.Qt.BottomToolBarArea,cf_bar)

        winMenu = self.winMenu = self.menuBar().addMenu("&Window")
        winMenu.addAction("Cl&ose",mdiArea.closeActiveSubWindow)
        winMenu.addAction("Close&All",mdiArea.closeAllSubWindows)
        winMenu.addAction("&Tile",mdiArea.tileSubWindows)

        cascadeAction = winMenu.addAction("&Cascade",self.cascadeSubWindows)
        cascadeAction.triggered.connect(mdiArea.cascadeSubWindows,Q.Qt.DirectConnection)
        winMenu.addAction("Ne&xt",mdiArea.activateNextSubWindow,Q.QKeySequence.NextChild)
        winMenu.addAction("&Prev",mdiArea.activatePreviousSubWindow,Q.QKeySequence.PreviousChild)
        mdiArea.subWindowActivated.connect(lambda : self.playlist.setPlayer(mdiArea.activeSubWindow()),Q.Qt.DirectConnection)
        self.destroyed.connect(self.shutdown,Q.Qt.DirectConnection)
        self._timer = Q.QTimer()
        self._timer.setInterval(int(1000/10))
#        self._timer.setTimerType(Q.Qt.PreciseTimer)
        self._timer.timeout.connect(self.update,Q.Qt.DirectConnection)
        self._timer.start()
        frate = kwargs.pop('forcerate',None)
        self._use_tabs = bool(int(kwargs.pop('use_tabs',self._use_tabs)))
        self._use_mdi  = bool(int(kwargs.pop('use_mdi',self._use_mdi)))
        if frate:
            try: self.forcedFrameRate = float(frate)
            except: pass
        self._options,media = AVPlayer.get_options(*args)
        print('options: ',self._options)
        p = self.getPlayerAt(-1)
        self.playlist.setPlayer(p)
        if media:
            self.playlist.updateActions()
            list(map(self.playlist.onRequestFile,media))
    @property
    def forcedFrameRate(self):
        return 1000 / self._timer.interval()

    @forcedFrameRate.setter
    def forcedFrameRate(self, val):
       self._timer.setInterval(int(1000/val))

    def makeWidgetFor(self,*args, **kwargs):
        try:
            plst = [self.playlist.item(i).path for i in range(self.playlist.count())] if self.playlist else []
            plst = [_.resolve().absolute().as_posix() for _ in plst if _]
#        print(plst)
            kwargs.update(self._options)
            print('args',args)
            print('kwargs',kwargs)
            cw = CtrlPlayer(*args, fp=plst,**kwargs)
            player = cw.childwidget
            for k,v in kwargs.items():
                try:
                    player.m.set_property(k,v)
                except:
                    pass

            if self._use_tabs:
                tw = Q.QTabWidget(parent=None)
                tw.addTab(cw,"video")

                cw.childwidget.resize(self.size())
#        if player._property_model is None:
#            player._property_model = AVTreePropertyModel(player=player,parent=player)
                tv = Q.QTreeView()
                if player._property_model is not None:
                    tv.setModel(player._property_model)
#            tv.setModel(player.getPropertyModel())
                player.propertyModelChanged.connect(lambda val:tv.setModel(val))
                tw.addTab(tv,"properties")
            else:
                tw = cw

            self._timer.timeout.connect(cw.update,Q.Qt.DirectConnection)
            player.index = self.next_id
            player._playlist = self.playlist
            self.next_id += 1
#        self.cascadeSubWindows.connect(cw.idealConfig)
#        self.crossfadeChanged.connect(cw.onCrossfadeChanged)
            if self._use_mdi:
                self.mdiArea.addSubWindow(tw)
                tw.adjustSize()
                tw.parent().adjustSize()
                tw.parent().update()
            else:
                mdi = Q.QMainWindow(parent=self,flags=Q.Qt.Dialog)
                mdi.show()
                mdi.raise_()
                mdi.setCentralWidget(tw)

            tw.destroyed.connect(tw.parent().close,Q.Qt.DirectConnection)
            tw.setVisible(True)
            player.playlist.forceUpdate()
            for _ in plst:
                player.try_command('loadfile',_,'append-play',_async=False)
#        if self.playlist:
#            for item in self.playlist.items():
#                print(item)
#                print(item.path,item.path.as_posix())
#                try:
#                    player.m.command('loadfile',item.path.as_posix(),'append-play',_async=False)
#                except:
#                    pass

            return player
        except BaseException as e:
            print(e)
            traceback.print_last()
