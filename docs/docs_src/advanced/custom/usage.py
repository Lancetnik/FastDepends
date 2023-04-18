from fast_depends import inject

@inject
def my_func(header_field: int = Header()):
    return header_field

assert h(
    headers={"header_field": "1"}
) == 1