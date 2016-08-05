#!/usr/bin/env python
import sys
import signal
import mpv
import locale
locale.setlocale(locale.LC_NUMERIC,'C')
from qtapp import App

signal.signal(signal.SIGINT, signal.SIG_DFL)

def main(args):
    return App(args).run()

if __name__ == '__main__':
    exit(main(sys.argv) or 0)
