#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from functools import partial,partialmethod
import sys
import av_player
import pathlib
class PlayListItem(Q.QListWidgetItem):
    def __init__(self,parent, path,*args,**kwargs):
        super().__init__(parent, *args,**kwargs)
        if path:
            self.path = pathlib.Path(path).resolve().absolute()
            self.setText(self.path.resolve().name)
#        self.path = pathlib.Path(path) if path else None
#        self.setText(posixpath.basename(self.path))

class PlayList(Q.QListWidget):
    requestPlaylistPos = Q.pyqtSignal(object)
    requestFile = Q.pyqtSignal(object)
    playerChanged = Q.pyqtSignal(object)
    def __loadfileAction(self, where):
        ci = self.currentItem()
        if not ci or not ci.path:
            return
        filePath = ci.path
        print(filePath)
        if not isinstance(where,av_player.AVPlayer):
            where = self._parent.getPlayerAt(where)
        for idx, it in enumerate(where.playlist.value()):
            if filePath.samefile(it['filename']):
                where.m.playlist_pos = idx
                return
        where.try_command('loadfile',filePath.as_posix(), 'append-play')
#        w = where.widget
#        if w: w.sized_once = False
#        if w:
#            w.idealConfig()
#            w.show()
        for idx, it in enumerate(where.playlist.value()):
            if filePath.samefile(it['filename']):
                where.playlist_pos.setValue(idx)
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

        if self.player and isinstance(self.player,av_player.AVPlayer):
            self.player.playlist.valueChanged.connect(self.onPlaylistChanged)
            self.player.playlist_pos.valueChanged.connect(self.onPlaylist_posChanged)
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
            a = Q.QAction("Load to player {}".format(p.index),self)
            a.triggered.connect(partial(self.__loadfileAction,p))
            self.addAction(a)
        self.playerChanged.emit(self.player)

    def setPlayer(self, p):
        if isinstance(p,Q.QMdiSubWindow):
            p = p.widget()
            if p:
                p = p.findChild(av_player.AVPlayer)
        if self.player is p:
            return
        if self.player:
            try: self.player.playlist.valueChanged.disconnect(self.onPlaylistChanged)
            except: pass
            try: self.player.playlist_pos.valueChanged.disconnect(self.onPlaylist_posChanged)
            except: pass

        self.clear()
        self.player = p
        if p:
            self.player.playlist.valueChanged.connect(self.onPlaylistChanged)
            self.player.playlist_pos.valueChanged.connect(self.onPlaylist_posChanged)
            self.player.playlist.valueChanged.emit(self.player.playlist.value())
        self.playerChanged.emit(p)
    def openFileNear(self):
        if not self.player:
            self.player = self.parent.getPlayerAt(-1)
        ci = self.currentItem()
        if ci and ci.path:
            filePath = pathlib.Path(ci.path)
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
#                w = self.player.widget
#                if w:w.sized_once = False
#                    w.idealConfig()
#                    w.show()
    def openUrl(self):
        urlPath, ok = Q.QInputDialog.getText(self,"Select URL.","ytdl://.....")
        if ok and urlPath:
            if not self.player:
#                return
                self.setPlayer(self._parent.makeWidgetFor(-1))
            print("\n"+urlPath+"\n")
            self.player.command("loadfile",str(urlPath),"append-play")
#            w = self.player.widget
#            if w:w.sized_once = False
#                    w.idealConfig()
#                    w.show()
    @Q.pyqtSlot(object)
    def onPlaylistChanged(self,playlist):
        for i, item in enumerate(playlist):
            existingitem = self.item(i)
            if not existingitem or not existingitem.path.samefile(item['filename']):
                self.insertItem(i,PlayListItem(self, item['filename']))

    @Q.pyqtSlot(object)
    def onPlaylist_posChanged(self,playlist_pos):
        if playlist_pos is not None:
            self.setCurrentRow(playlist_pos)
        else:
            self.setCurrentRow(0)

    @Q.pyqtSlot(object)
    def onRequestFile(self,path):
        self.player.command("loadfile",path,"append-play")

    @Q.pyqtSlot("QListWidgetItem*")
    def on_clicked(self,item):
        if self.player:
            row = self.row(item)
            if row >= 0 and row < self.player.playlist_count.value():
                self.player.playlist_pos.setValue(row)
