#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
from functools import partial
import sys
if sys.version_info.major > 2: basestring = str
class PlayListItem(Q.QListWidgetItem):
    def __init__(self,parent, path,*args,**kwargs):
        super(self.__class__,self).__init__(parent, *args,**kwargs)
        import posixpath
        self.path = path
        self.setText(posixpath.basename(self.path))

class PlayList(Q.QListWidget):
    requestPlaylistPos = Q.pyqtSignal(object)
    requestFile = Q.pyqtSignal(object)
    def __init__(self,parent,player,*args,**kwargs):
        super(self.__class__,self).__init__(*args,**kwargs)
        self.player = player
        self.players= parent.players
        self.player.playlistChanged.connect(self.onPlaylistChanged)
        self.player.playlist_posChanged.connect(self.onPlaylist_posChanged)
        self.itemDoubleClicked.connect(self.on_clicked)
        self.setContextMenuPolicy(Q.Qt.ActionsContextMenu)
        def act(p,self):
            filePath = str(self.currentItem().path)
            print(filePath)
            for idx, it in enumerate(p.m.playlist):
                if it['filename'] == filePath:
                    p.m.playlist_pos = idx
                    return
            p.command('loadfile',filePath, 'append-play')
            for idx, it in enumerate(p.m.playlist):
                if it['filename'] == filePath:
                    p.m.playlist_pos = idx
                    return

        for i,p in enumerate(self.players):
            action = Q.QAction("Load to player {}".format(i),self)
            action.triggered.connect(partial(act,p,self))
            self.addAction(action)
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
        if fileDialog.exec_():
            for filePath in fileDialog.selectedFiles():
                print("\n"+filePath+"\n")
                self.player.command("loadfile",str(filePath),"append-play")
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
