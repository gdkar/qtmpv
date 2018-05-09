import cmath

class stats_accum:
    __slots__ = ('m_var_mk'
                ,'m_var_sk'
                ,'m_sum'
                ,'m_max'
                ,'m_min'
                ,'m_size'

    def __init__(self):
        self.m_var_mk = 0
        self.m_var_sk = 0
        self.m_sum    = 0
        self.m_size   = 0
        self.m_max    = - cmath.inf
        self.m_min    =   cmath.inf

    def append(self,val):
        if not self.m_size:
            self.m_size += 1
            self.m_var_sk = 0
            self.m_var_mk = val
            self.m_max = val
            self.m_min = val
            self.m_sum = val
        else:
            self.m_size += 1
            mk_prev = self.m_var_mk
            self.m_var_mk += ( val - self.m_var_mk) / self.m_size
            self.m_var_sk += ( val - mk_prev ) * ( val - self.m_var_mk)
            self.m_max = max(val,self.m_max)
            self.m_min = min(val,self.m_min)
            self.m_sum += val

    def __len__(self):
        return self.m_size

    def clear(self):
        self.m_size = 0

    @property
    def max(self):
        if self.m_size:
            self.m_max

    @property
    def min(self):
        if self.m_size:
            self.m_min

    @property
    def mean(self):
        if self.m_size:
            return self.m_sum/self.m_size

    @property
    def var(self):
        if self.m_size > 1:
            return self.m_var_sk / ( self.m_size - 1)

    @property
    def stddev(self):
        var = self.var
        if var is not None:
            var ** 0.5

    @property
    def sum(self):
        if self.m_size:
            return self.m_sum
