import asyncio
import functools
import inspect
import threading
from typing import Awaitable, Callable, TypeVar, Union

T = TypeVar("T")

if hasattr(asyncio, "to_thread"):
    to_thread = asyncio.to_thread
else:
    # Copy of python 3.9, asyncio.to_thread as it is not available pre 3.9 .
    import contextvars
    from asyncio import events

    async def to_thread(func, /, *args, **kwargs):
        loop = events.get_running_loop()
        ctx = contextvars.copy_context()
        func_call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)


def sync(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]], *args, **kwargs
) -> T:
    """
    Run the given function `func` on the given `args` and `kwargs`,
    synchronously even if it was asynchronous . Returns the evaluated (not
    awaitable) result of the function.
    """

    if inspect.iscoroutinefunction(func):
        try:
            # If loop not running, will be able to run a new one until complete.
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(func(*args, **kwargs))

        except Exception:
            # If loop is already running, will hit exception so create one in a
            # new thread instead.

            def in_thread(func, *args, **kwargs):
                th = threading.current_thread()
                th.ret = None
                th.exc = None

                loop = asyncio.new_event_loop()
                try:
                    th.ret = loop.run_until_complete(func(*args, **kwargs))
                except Exception as e:
                    th.exc = e

            th = threading.Thread(
                target=in_thread, args=(func, *args), kwargs=kwargs
            )

            th.start()

            # Will block.
            th.join()

            if th.exc is not None:
                raise th.exc
            else:
                return th.ret

    else:
        # If not coroutinefunction, run it without loop.

        return func(*args, **kwargs)


def desync(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]], *args, **kwargs
) -> Awaitable[T]:
    """
    Produce the awaitable of the given function's, `func`, run on the given
    `args` and `kwargs`, asynchronously, and return its awaitable of the result.
    """

    if inspect.iscoroutinefunction(func):
        return func(*args, **kwargs)
    else:
        return to_thread(func, *args, **kwargs)


def synced(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]]
) -> Callable[..., T]:
    """
    Produce a synced version of the given function `func`. If `func` returns an
    awaitable, the synced version will return the result of that awaitable
    instead. If the given function was not asynchronous, returns it as is.
    """

    if not inspect.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return sync(*args, func=func, **kwargs)

    return wrapper


def desynced(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]]
) -> Callable[..., Awaitable[T]]:
    """
    Return a desynced version of the given func. The desynced function returns
    an awaitable of what the original returned. If the given function was
    already asynchronous, returns it as is. That is, it will not wrap the
    awaitable in another layer of awaitable.
    """

    if inspect.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return desync(*args, func=func, **kwargs)

    return wrapper
