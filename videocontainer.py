#from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
import sys
if sys.version_info.major > 2: basestring = str
class VideoContainer(QW.QWidget):
    def sizeHint(self):
        if not self.vwidth:return QW.QWidget.sizeHint(self)
        return Q.QSize(self.vwidth, self.vheight)
    def __init__(self, parent):
        super(self.__class__,self).__init__(parent)
        self.vwidth = None
        self.vheight = None
        self.childwin = Q.QWindow()
        self.childwidget = Q.QWidget.createWindowContainer(self.childwin)
        self.layout = Q.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.childwidget)
        self.setLayout(self.layout)
