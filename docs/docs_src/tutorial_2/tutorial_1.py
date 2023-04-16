class MyClass: pass

MyClass()       # It is a "call"!      1-st call


class MyClass:
    def __call__(): pass

m = MyClass()
m()             # It is a "call" too!  2-nd call


class MyClass:
    @classmethod
    def f(): pass

MyClass.f()     # Yet another "call"!  3-rd call


class MyClass
    def f(self): pass

MyClass().f()   # "call"?              4-th call