from glproxy import gl, glx
from PyQt5 import Qt as Q, QtWidgets as QW, QtGui as QG
import sys
if sys.version_info.major > 2: basestring = str
class VideoOpenGLWidget(Q.QOpenGLWidget):
    def __init__(self,parent,*args,**kwargs):
        super(self.__class__,self).__init__(*args,parent=parent,**kwargs)
        self.fmt = Q.QSurfaceFormat.defaultFormat()
        self.fmt.setSamples(8)
        self.setFormat(self.fmt)
        self.wwidth      = None
        self.wheight     = None
        self.childwin    = Q.QWindow()
        self.childwidget = Q.QWidget.createWindowContainer(self.childwin)
        self.layout      = Q.QHBoxLayout()
#        self.layout.setContainsMargins(0,0,0,0)
        self.setLayout(self.layout)
    def sizeHint(self):
        if not self.wwidth: return Q.QWidget.sizeHint(self)
        return Q.QSize(self.wwidth,self.wheight)
    def initializeGL(self):
        self.context = Q.QOpenGLContext.currentContext()
        gl.clearColor(0,0,0,0)
        gl.enable(gl.TEXTURE_2D)
        self.tex_id = gl.genTextures(1)
        gl.bindTexture(gl.TEXTURE_2D,self.tex_id)
        gl.texParameter(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR)
        gl.texParameter(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR)
        print("Generated Texture ID {}".format(self.tex_id))
