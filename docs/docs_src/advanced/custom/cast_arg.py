class Header(CustomField):
    def __init__(self):
        super().__init__(cast=True)


class NotCastHeader(CustomField):
    def __init__(self):
        super().__init__(cast=False)


def func(
    h1: int = Header(),        # <-- casts to int
    h2: int = NotCastHeader()  # <-- just an annotation
): ...