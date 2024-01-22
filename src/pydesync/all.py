import asyncio
import functools
import inspect
import threading
from typing import Any, Awaitable, Callable, TypeVar, Union

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


def iscoroutinefunction_or_wrapper(func: Any) -> bool:
    if inspect.iscoroutinefunction(func):
        return True

    # Sometimes __wrapped__ is not coroutinefunction even if func is so the
    # check above comes first.
    if hasattr(func, "__wrapped__"):
        # See
        # https://docs.python.org/3/library/functools.html#functools.update_wrapper
        # . Async functions wrapped by functools are not recognized as
        # coroutinefunction.
        return inspect.iscoroutinefunction(func.__wrapped__)
    else:
        return False


def sync(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]], *args, **kwargs
) -> T:
    """
    Run the given function `func` on the given `args` and `kwargs`,
    synchronously even if it was asynchronous . Returns the evaluated (not
    awaitable) result of the function.
    """

    maybe_awaitable = func(*args, **kwargs)

    if inspect.isawaitable(maybe_awaitable):
        maybe_awaitable: Awaitable

        try:
            # If loop not running, will be able to run a new one until complete.
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(maybe_awaitable)

        except Exception:
            # If loop is already running, will hit exception so create one in a
            # new thread instead.

            def in_thread(awaitable):
                th = threading.current_thread()
                th.ret = None
                th.exc = None

                loop = asyncio.new_event_loop()
                try:
                    th.ret = loop.run_until_complete(awaitable)
                except Exception as e:
                    th.exc = e

            th = threading.Thread(
                target=in_thread, args=(maybe_awaitable,)
            )

            th.start()

            # Will block.
            th.join()

            if th.exc is not None:
                raise th.exc
            else:
                return th.ret

    else:
        # If not awaitable, return it without futher evaluation.

        return maybe_awaitable


def desync(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]], *args, **kwargs
) -> Awaitable[T]:
    """
    Produce the awaitable of the given function's, `func`, run on the given
    `args` and `kwargs`, asynchronously, and return its awaitable of the result.
    """

    if iscoroutinefunction_or_wrapper(func):
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

    if not iscoroutinefunction_or_wrapper(func):
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

    if iscoroutinefunction_or_wrapper(func):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return desync(*args, func=func, **kwargs)

    return wrapper
