#! /usr/bin/env python3.6
from __future__ import print_function, division,  absolute_import
import argparse, ctypes, sys, pprint, time, mpv
import signal
from interruptingcow import SignalWakeupHandler

import posix,posixpath

if sys.version_info.major > 2:
    basestring = str
from modproxy import ModuleProxy
from glproxy  import gl, glx
from qtproxy import Q, QW, QG
#from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG

from topwindow import TopWindow
#from player import Player

if __name__ == '__main__':
#    Q.QSurfaceFormat.setDefaultFormat(fmt)
    app = Q.QApplication(sys.argv)

#    player = Player()
    args = list()
    kwargs = dict()
    for arg in sys.argv[1:]:
        if '=' in arg:
            parts = arg.partition('=')
            kwargs[parts[0]] = parts[2]
        else:
            args.append(arg)

    with SignalWakeupHandler(app):
        signal.signal(signal.SIGINT, lambda *a:app.quit())

        win = TopWindow(*args, **kwargs)
        fmt = Q.QOpenGLContext.globalShareContext().format()
        print('OpenGLFormat:\n')
        print('version={}'.format(fmt.version()))
        print('samples={}'.format(fmt.samples()))
        print('redBufferSize={}'.format(fmt.redBufferSize()))
        print('greenBufferSize={}'.format(fmt.greenBufferSize()))
        print('blueBufferSize={}'.format(fmt.blueBufferSize()))
        print('alphaBufferSize={}'.format(fmt.alphaBufferSize()))
        print('depthBufferSize={}'.format(fmt.depthBufferSize()))
        print('stencilBufferSize={}'.format(fmt.stencilBufferSize()))
        print('swapBehavior={}'.format(fmt.swapBehavior()))
        print('swapInterval={}'.format(fmt.swapInterval()))
        print('debugContext={}'.format(fmt.testOption(fmt.DebugContext)))
        print('deprecatedFunctions={}'.format(fmt.testOption(fmt.DeprecatedFunctions)))
        print('renderable={}'.format(fmt.renderableType()))
        app.aboutToQuit.connect(win.close)
        win.show()
        sys.exit(app.exec_())
