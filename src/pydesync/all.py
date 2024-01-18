import asyncio
import functools
import inspect
import sys
import threading
import time
from datetime import datetime
from typing import Awaitable, Callable, TypeVar, Union

A = TypeVar("A")
B = TypeVar("B")

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
    func: Union[Callable[[A], B], Callable[[A], Awaitable[B]]], *args, **kwargs
) -> B:
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
    func: Union[Callable[[A], B], Callable[[A], Awaitable[B]]], *args, **kwargs
) -> Awaitable[B]:
    """
    Produce the awaitable of the given function's, `func`, run on the given
    `args` and `kwargs`, asynchronously, and return its awaitable of the result.
    """

    if inspect.iscoroutinefunction(func):
        return func(*args, **kwargs)
    else:
        return to_thread(func, *args, **kwargs)


def synced(
    func: Union[Callable[[A], B], Callable[[A], Awaitable[B]]]
) -> Callable[[A], B]:
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
    func: Union[Callable[[A], B], Callable[[A], Awaitable[B]]]
) -> Callable[[A], Awaitable[B]]:
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


if "pytest" in sys.modules:
    import pytest

    class Tests:
        SHORT_TIME = 0.1

        @staticmethod
        async def _async_sleep_some_and_return_negation(i: int):
            """
            Function that blocks (asynchronously) for `SHORT_TIME` seconds
            before returning the negation of its integer input.
            """

            await asyncio.sleep(Tests.SHORT_TIME)
            return -i

        @staticmethod
        def _sleep_some_and_return_negation(i: int):
            """
            Function that blocks for `SHORT_TIME` seconds before returning the
            negation of its integer input.
            """

            time.sleep(Tests.SHORT_TIME)
            return -i

        def _test_sync(self, func):
            """
            Test that func can run and produce the correct result. Assumes it is
            some wrapping of one of the two sleepy functions above.
            """
            total = sum(func(i=i) for i in range(10))

            # Answer is correct.
            assert total == -(9 * 10 // 2)  # n * (n+1) / 2 for n = 9

        async def _test_async(self, func):
            """
            Test that func can run in parallel. Assumes it is some wrapping of
            one of the two sleepy functions above.
            """
            starting_time = datetime.now()

            total = sum(await asyncio.gather(*(func(i=i) for i in range(10))))

            ending_time = datetime.now()

            # Answer is correct.
            assert total == -(9 * 10 // 2)  # n * (n+1) / 2 for n = 9

            # Ran in parallel. Factor of 1.1 for some wiggle room for overheads.
            # Would have been Tests.SHORT_TIME * 10 if it ran sequentially.
            assert (
                ending_time - starting_time
            ).seconds < Tests.SHORT_TIME * 1.1

        @pytest.mark.asyncio
        async def test_test_funcs(self):
            """
            Test that the test methods above do what they are supposed to
            without invoking sync/desync yet.
            """

            await self._test_async(Tests._async_sleep_some_and_return_negation)
            self._test_sync(Tests._sleep_some_and_return_negation)

        def test_sync(self):
            """
            Test a `sync` on an asynchronous sleeper. Checks that it produces
            the expected results only.
            """
            self._test_sync(
                lambda i:
                sync(Tests._async_sleep_some_and_return_negation, i=i)
            )

        def test_synced(self):
            """
            Test a `synced` on an asynchronous sleeper. Checks that it produces
            the expected results only.
            """
            self._test_sync(
                synced(Tests._async_sleep_some_and_return_negation)
            )

        @pytest.mark.asyncio
        async def test_desync(self):
            """
            Test `desync` on the synchronous sleeper. Checks that it produces
            the expected result and runs in parallel based on time to return 10
            parallel invocations.
            """

            await self._test_async(
                lambda i: desync(Tests._sleep_some_and_return_negation, i=i)
            )

        @pytest.mark.asyncio
        async def test_desynced(self):
            """
            Test `desynced` on the synchronous sleeper. Checks that it produces
            the expected result and runs in parallel based on the time to return
            10 parallel invocations.
            """

            await self._test_async(
                desynced(Tests._sleep_some_and_return_negation)
            )

        @pytest.mark.asyncio
        async def test_readme_example(self):
            """
            Test the example from `README.md`.
            """

            def wait_some():
                time.sleep(1)
                return 1

            # This should take approx. 1 second:
            assert 10 == sum(
                await asyncio.gather(*(desync(wait_some) for i in range(10)))
            )
