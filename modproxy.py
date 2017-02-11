import sys

class ModuleProxy(object):
    def __init__(self,name):
        self.name = name.split('.')[-1].lower() if '.' in name else name.lower()
        self.module = __import__(name)
        if '.' in name:
            for seg in name.split('.')[1:]:
                self.module = getattr(self.module,seg)
    def __getattr__(self,name):
        attr = getattr(self.module,self.name.upper() + '_' + name) if name.isupper() else \
             getattr(self.module,self.name+''.join([x[0].upper()+x[1:] for x in name.split('_')]))
        setattr(self,name,attr)
        return attr

