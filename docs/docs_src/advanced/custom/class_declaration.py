from fast_depends.library import CustomField

class Header(CustomField):
    def use(self, **kwargs: AnyDict) -> AnyDict:
        kwargs = super().use(**kwargs)
        kwargs[self.param_name] = kwargs["headers"][self.param_name]
        return kwargs
