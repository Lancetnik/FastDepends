from fast_depends import Depends, dependency_provider, inject

def original_dependency():
    raise NotImplementedError()

def override_dependency():
    return 1

@inject
def func(d = Depends(original_dependency)):
    return d

dependency_provider.override(original_dependency, override_dependency)
# or
dependency_provider[original_dependency] = override_dependency

def test():
    assert func() == 1
