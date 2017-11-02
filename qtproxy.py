#! /usr/bin/env python3.6
from __future__ import print_function, division,  absolute_import

import posix,posixpath,sys

if sys.version_info.major > 2:
    basestring = str

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui  import QSurfaceFormat

fmt = QSurfaceFormat.defaultFormat()
fmt.setVersion(4,5)
fmt.setProfile(QSurfaceFormat.CoreProfile)
fmt.setSamples(0)

QSurfaceFormat.setDefaultFormat(fmt)
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from PyQt5 import Qt as Q, QtCore as QC, QtWidgets as QW, QtGui as QG, QtOpenGL as QOGL
