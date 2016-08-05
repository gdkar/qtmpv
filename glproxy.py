from modproxy import ModuleProxy
class GLProxy(ModuleProxy):
    from contextlib import contextmanager
    @contextmanager
    def matrix(self):
        self.module.glPushMatrix()
        try: yield
        finally:self.module.glPopMatrix()
    @contextmanager
    def attrib(self, *args):
        mask = 0
        for arg in args:
            if isinstance(arg,basestring):arg = getattr(selfmodule,'GL_{}_BIT'.format(arg.upper()))
            mask |= arg
        self.module.glPushAttrib(mask)
        try:yield
        finally: self.module.glPopAttrib()
    def enable(self, *args, **kwargs):
        self.__enable(True,*args,**kwargs)
        return self.__apply_on_exit(self.__enable,False,*args,**kwargs)
    def disable(self,*args,**kwaargs):
        self.__enable(False,*args,**kwargs)
        return self.__apply_on_exit(self.__enable,True,*args,**kwargs)
    def __enable(self,enable,*args,**kwargs):
        todo = list()
        for arg in args:
            if isinstance(arg,basestring):arg = getattr(self.module,'GL_{}'.format(arg.upper()))
            if arg: todo.append((arg,enable))
        for key,value in kwargs.iteritems():
            flag = getattr(self.module,'GL_{}'.format(key.upper()))
            value= value if enable else not value
            todo.append((flag,value))
        for flag,value in todo:
            if value:
                self.module.glEnable(flag)
            else:
                self.module.glDisable(flag)
    def begin(self,arg):
        if isinstance(arg,basestring):arg = getattr(self.module,'GL_{}'.format(arg.upper()))
        if arg: 
            self.module.glBegin(arg)
            return self.__apply_on_exit(self.module.glEnd)
    @contextmanager
    def __apply_on_exit(self,func,*args,**kwargs):
        try: yield
        finally: func(*args,**kwargs)
gl   = GLProxy('OpenGL.GL')
#glu  = ModuleProxy('OpenGL.GLU')
glx  = ModuleProxy('OpenGL.GLX')
#glut = ModuleProxy('OpenGL.GLUT')

