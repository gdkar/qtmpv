#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from functools import partial,partialmethod
import sys
import player
class PlayListItem(Q.QListWidgetItem):
    def __init__(self,parent, path,*args,**kwargs):
        super().__init__(parent, *args,**kwargs)
        import posixpath
        self.path = path
        self.setText(posixpath.basename(self.path))

class PlayList(Q.QListWidget):
    requestPlaylistPos = Q.pyqtSignal(object)
    requestFile = Q.pyqtSignal(object)
    def __loadfileAction(self, where):
        ci = self.currentItem()
        if not ci or not ci.path:
            return
        filePath = str(self.currentItem().path)
        print(filePath)
        if not isinstance(where,player.Player):
            where = self._parent.getPlayerAt(where)
        for idx, it in enumerate(where.m.playlist):
            if it['filename'] == filePath:
                where.m.playlist_pos = idx
                return
        where.command('loadfile',filePath, 'append-play')
        w = where.widget
        if w: w.sized_once = False
#        if w:
#            w.idealConfig()
#            w.show()
        for idx, it in enumerate(where.m.playlist):
            if it['filename'] == filePath:
                where.m.playlist_pos = idx
                return
    @property
    def players(self):
        return self._parent.players

    def __init__(self,parent,player,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.player = None
        self._parent = parent
        self.itemDoubleClicked.connect(self.on_clicked)
        self.setContextMenuPolicy(Q.Qt.ActionsContextMenu)
        self.updateActions()

        if self.player:
            self.player.playlistChanged.connect(self.onPlaylistChanged)
            self.player.playlist_posChanged.connect(self.onPlaylist_posChanged)


    def updateActions(self):
        acts = self.actions()
        for a in acts:
            if a: self.removeAction(a)
        a = Q.QAction("Load to new &player",self)
        a.triggered.connect(partial(self.__loadfileAction,-1))
        self.addAction(a)
        for i,p in enumerate(self.players):
            a = Q.QAction("Load to player {}".format(i),self)
            a.triggered.connect(partial(self.__loadfileAction,p))
            self.addAction(a)

    def setPlayer(self, player):
        if self.player:
            self.player.playlistChanged.disconnect(self.onPlaylistChanged)
            self.player.playlist_posChanged.disconnect(self.onPlaylist_posChanged)
        self.clear()
        self.player = player
        if player:
            self.player.playlistChanged.connect(self.onPlaylistChanged)
            self.player.playlist_posChanged.connect(self.onPlaylist_posChanged)
            self.player.playlistChanged.emit(self.player.m.playlist)

    def openFile(self):
        if not self.player:
            return
        fileDialog = Q.QFileDialog(self)
        fileDialog.setAcceptMode(Q.QFileDialog.AcceptOpen)
        fileDialog.setFileMode(Q.QFileDialog.ExistingFiles)
        fileDialog.setFilter(Q.QDir.Hidden|Q.QDir.AllEntries|Q.QDir.System)
        fileDialog.setViewMode(Q.QFileDialog.Detail)
        fileDialog.setDirectory(Q.QDir.home().canonicalPath())
        if fileDialog.exec():
            if fileDialog.selectedFiles():
                for filePath in fileDialog.selectedFiles():
                    print("\n"+filePath+"\n")
                    self.player.command("loadfile",str(filePath),"append-play")
                w = self.player.widget
                if w:w.sized_once = False
#                    w.idealConfig()
#                    w.show()

    @Q.pyqtSlot(object)
    def onPlaylistChanged(self,playlist):
        for i, item in enumerate(playlist):
            existingitem = self.item(i)
            if not existingitem or existingitem.path != item['filename']:
                self.insertItem(i,PlayListItem(self, item['filename']))

    @Q.pyqtSlot(int)
    def onPlaylist_posChanged(self,playlist_pos):
        self.setCurrentRow(playlist_pos)

    @Q.pyqtSlot(object)
    def onRequestFile(self,path):
        self.player.command("loadfile",path,"append-play")

    @Q.pyqtSlot("QListWidgetItem*")
    def on_clicked(self,item):
        self.player.m.playlist_pos = self.row(item)
