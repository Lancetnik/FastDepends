from typing import Sequence

from fast_depends.types import AnyDict, P


def args_to_kwargs(
    arguments: Sequence[str], *args: P.args, **kwargs: P.kwargs
) -> AnyDict:
    if not args:
        return kwargs

    unused = filter(lambda x: x not in kwargs, arguments)

    return dict((*zip(unused, args), *kwargs.items()))
