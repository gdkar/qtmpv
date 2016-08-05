from PyQt5 import (
        Qt as Q,
        QtWidgets as QW,
        QtGui as QG,
        )
import sys
if sys.version_info.major > 2: basestring = str
class DisplayWidget(Q.QLabel):
    def __init__ ( self, *args, **kwargs):
        super(self.__class__,self).__init__(*args,**kwargs)
        self.setMinimumSize(192,108)
        size_policy = Q.sizePolicy(Q.sizePolicy.Preferred,Q.sizePolicy.Preferred)
        size_policy.setHeightForWidth(True)
        sself.setAlignment(Q.Qt.AlignHCenter|Q.Qt.AlignBottom)
        self.pixmap = None
        self.setMargin(0)
    def heighForWidth(self):
        return width * 9 / 16.
