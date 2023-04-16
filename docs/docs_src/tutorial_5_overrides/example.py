from fast_depends import Depends, inject, dependency_provider

def original_dependency():
    return 1

def override_dependency():
    return 2

dependency_provider.override(original_dependency, override_dependency)
# or
dependency_provider.dependency_overrides[original_dependency] = override_dependency

def test():
    @inject
    def func(d = Depends(original_dependency)):
        return d

    assert func() == 2
