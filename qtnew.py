#! /usr/bin/env python
from __future__ import print_function, division,  absolute_import
import argparse, ctypes, sys, pprint, time, mpv

import posix,posixpath

if sys.version_info.major > 2:
    basestring = str

from modproxy import ModuleProxy
from glproxy  import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG

from player import Player

from topwindow import TopWindow

if __name__ == '__main__':
    app = Q.QApplication(sys.argv)
#    player = Player()
    win = TopWindow(2,*sys.argv[1:])
    win.show()
    app.exec_()
