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
        filePath = str(ci.path)
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
        self.setAttribute(Q.Qt.WA_DeleteOnClose)
        self.player = None
        self._parent = parent
        self.itemDoubleClicked.connect(self.on_clicked)
        self.setContextMenuPolicy(Q.Qt.ActionsContextMenu)
        self.updateActions()

        if self.player and isinstance(self.player,player.Player):
            self.player.playlistChanged.connect(self.onPlaylistChanged)
            self.player.playlist_posChanged.connect(self.onPlaylist_posChanged)


    def updateActions(self):
        acts = self.actions()
        for a in acts:
            if a:
                self.removeAction(a)
        a = Q.QAction("&Open near",self)
        a.triggered.connect(self.openFileNear)
        self.addAction(a)
        a = Q.QAction("Load to new &player",self)
        a.triggered.connect(partial(self.__loadfileAction,-1))
        self.addAction(a)
        for p in self.players:
            if not p.widget:
                continue
            a = Q.QAction("Load to player {}".format(p.index),self)
            a.triggered.connect(partial(self.__loadfileAction,p))
            self.addAction(a)

    def setPlayer(self, p):
        if isinstance(p,Q.QMdiSubWindow):
            p = p.widget()
            if p:
                p = p.player
        if self.player:
            try: self.player.playlistChanged.disconnect(self.onPlaylistChanged)
            except: pass
            try: self.player.playlist_posChanged.disconnect(self.onPlaylist_posChanged)
            except: pass

        self.clear()
        self.player = p
        if p:
            self.player.playlistChanged.connect(self.onPlaylistChanged)
            self.player.playlist_posChanged.connect(self.onPlaylist_posChanged)
            self.player.playlistChanged.emit(self.player.m.playlist)

    def openFileNear(self):
        if not self.player:
            self.player = self.parent.getPlayerAt(-1)
        ci = self.currentItem()
        if ci and ci.path:
            filePath = str(ci.path)
        else:
            filePath = None
        prev,self.player = self.player, None
        self.openFile(filePath)
        self.player = prev

    def openFile(self, near = None):
        fileDialog = Q.QFileDialog(self)
        fileDialog.setAcceptMode(Q.QFileDialog.AcceptOpen)
        fileDialog.setFileMode(Q.QFileDialog.ExistingFiles)
        fileDialog.setFilter(Q.QDir.Hidden|Q.QDir.AllEntries|Q.QDir.System)
        fileDialog.setViewMode(Q.QFileDialog.Detail)
        if near is not None:
            if isinstance(near,str):
                near = Q.QFileInfo(near)
            if isinstance(near,Q.QFileInfo):
                if near.isDir():
                    near = Q.QDir(near.filePath())
                else:
                    near = near.dir()
        if not isinstance(near,Q.QDir):
            near = Q.QDir.home()
        fileDialog.setDirectory(near.canonicalPath())
        if fileDialog.exec():
            if fileDialog.selectedFiles():
                if not self.player:
#                    return
                    self.player = self._parent.getPlayerAt(-1)
                for filePath in fileDialog.selectedFiles():
                    print("\n"+filePath+"\n")
                    self.player.command("loadfile",str(filePath),"append-play")
                w = self.player.widget
                if w:w.sized_once = False
#                    w.idealConfig()
#                    w.show()
    def openUrl(self):
        urlPath, ok = Q.QInputDialog.getText(self,"Select URL.","ytdl://.....")
        if ok and urlPath:
            if not self.player:
#                return
                self.setPlayer(self._parent.getPlayerAt(-1))
            print("\n"+urlPath+"\n")
            self.player.command("loadfile",str(urlPath),"append-play")
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
