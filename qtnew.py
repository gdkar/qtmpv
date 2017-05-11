#! /usr/bin/env python3.6
from __future__ import print_function, division,  absolute_import
import argparse, ctypes, sys, pprint, time, mpv

import posix,posixpath

if sys.version_info.major > 2:
    basestring = str
from modproxy import ModuleProxy
from glproxy  import gl, glx
from qtproxy import Q, QW, QG
#from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG

from topwindow import TopWindow
from player import Player

if __name__ == '__main__':
    app = Q.QApplication(sys.argv)
    player = Player()
    win = TopWindow(*sys.argv[1:])
    app.aboutToQuit.connect(win.close)
    win.show()
    app.exec_()
