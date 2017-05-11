#! /usr/bin/env python3.6
from __future__ import print_function, division,  absolute_import

import posix,posixpath,sys

if sys.version_info.major > 2:
    basestring = str

from PyQt5.QtCore import QCoreApplication, Qt


QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from PyQt5 import Qt as Q, QtCore as QC, QtWidgets as QW, QtGui as QG, QtOpenGL as QOGL
