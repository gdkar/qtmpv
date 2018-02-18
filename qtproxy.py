#! /usr/bin/env python3.6
from __future__ import print_function, division,  absolute_import

import posix,posixpath,sys, re

if sys.version_info.major > 2:
    basestring = str

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui  import QSurfaceFormat

fmt = QSurfaceFormat.defaultFormat()
fmt.setProfile(QSurfaceFormat.CoreProfile)
fmt.setRedBufferSize(8);
fmt.setGreenBufferSize(8);
fmt.setBlueBufferSize(8);
fmt.setAlphaBufferSize(8);
fmt.setDepthBufferSize(24);
fmt.setStencilBufferSize(8);

version_str = posix.environ.get(b'AV_PLAYER_OGL_VERSION',None)
version = None
if version_str:
    try:
        match = version_re.match(version_str)
        if match:
            version = (int(match.group(1)),int(match.group(2)))
    except:
        pass

if version is None:
    try:
        version = ( int(posix.environ.get(b'AV_PLAYER_OGL_VERSION_MAJOR',b'4')),
                    int(posix.environ.get(b'AV_PLAYER_OGL_VERSION_MINOR',b'5')))
    except: pass

if version is not None:
    try: fmt.setVersion(*version)
    except: pass


renderable = posix.environ.get(b'AV_PLAYER_OGL_RENDERABLE',None)

if renderable:
    renderable = renderable.decode('utf8')
    try:
        if hasattr(fmt, renderable):
            renderable = getattr(fmt,renderable)
        else:
            renderable = int(renderable)
        fmt.setRenderableType(renderable)
    except:
        pass

renderable = posix.environ.get(b'AV_PLAYER_OGL_SWAP_BEHAVIOR',b'DoubleBuffer')
if renderable:
    renderable = renderable.decode('utf8')
    try:
        if hasattr(fmt, renderable):
            renderable = getattr(fmt,renderable)
        else:
            renderable = int(renderable)
        fmt.setSwapBehavior(renderable)
    except:
        pass

try: fmt.setOption(fmt.DebugContext,int(posix.environ.get(b'AV_PLAYER_OGL_DEBUG_CONTEXT', b'0')))
except: pass
try: fmt.setSwapInterval(int(posix.environ.get(b'AV_PLAYER_OGL_SWAP_INTERVAL', b'0')))
except: pass
try: fmt.setSamples(int(posix.environ.get(b'AV_PLAYER_OGL_SAMPLES', b'0')))
except: pass

QSurfaceFormat.setDefaultFormat(fmt)
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from PyQt5 import Qt as Q, QtCore as QC, QtWidgets as QW, QtGui as QG, QtOpenGL as QOGL
