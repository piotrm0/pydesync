import functools
import asyncio
import inspect
import time
from typing import TYPE_CHECKING, TypeVar, Callable, Awaitable, Union
from datetime import datetime

A = TypeVar("A")
B = TypeVar("B")

if hasattr(asyncio, "to_thread"):
    to_thread = asyncio.to_thread
else:
    # Copy of python 3.9, asyncio.to_thread as it is not available pre 3.9 .
    from asyncio import events
    import contextvars
    async def to_thread(func, /, *args, **kwargs):
        loop = events.get_running_loop()
        ctx = contextvars.copy_context()
        func_call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)

def sync(
    func: Union[
        Callable[[A], B], 
        Callable[[A], Awaitable[B]]
    ],
    *args,
    **kwargs
) -> B:
    if inspect.iscoroutinefunction(func):
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(
                func(*args, **kwargs)
            )
        except Exception as e:
            raise (e)
            # TODO
    else:
        return func(*args, **kwargs)

async def desync(
    func: Union[
        Callable[[A], B], 
        Callable[[A], Awaitable[B]]
    ],
    *args,
    **kwargs
) -> B:
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return await to_thread(func, *args, **kwargs)

import sys
# Run tests only if running under pytest. Check this by testing that pytest has
# already been imported by someone else.
if "pytest" in sys.modules:
    import pytest

    class TestDesync():
        @staticmethod
        def _sleep_some_and_return_negation(i: int):
            """
            Function that blocks for 1 second before returning the negation of its
            integer input.
            """

            time.sleep(1)
            return -i

        async def _test_desync(self, func):
            """
            Test that func can run in parallel. Assumes it is some wrapping of
            _test_some_and_return_negation .
            """
            awaits = []

            starting_time = datetime.now()

            for i in range(10):
                awaits.append(func(i=i))

            total = 0
            for ret in await asyncio.gather(*awaits):
                total += ret

            ending_time = datetime.now()

            # Answer is correct.
            assert total == -(9 * 10 // 2) # n * (n+1) / 2 for n = 9

            # Ran in parallel.
            assert (ending_time - starting_time).seconds < 2.0

        @pytest.mark.asyncio
        async def test_desync(self):
            async def testfun(i):
                return await desync(TestDesync._sleep_some_and_return_negation, i=i)
            
            await self._test_desync(testfun)

        @pytest.mark.asyncio
        async def test_desynced(self):
            await self._test_desync(
                desynced(TestDesync._sleep_some_and_return_negation)
            )


def synced(
    func: Union[
        Callable[[A], B], 
        Callable[[A], Awaitable[B]]
    ]
) -> Callable[[A], B]:
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return sync(*args, func=func, **kwargs)
    
    return wrapper
    
def desynced(
    func: Union[
        Callable[[A], B], 
        Callable[[A], Awaitable[B]]
    ]
) -> Callable[[A], Awaitable[B]]:
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return desync(*args, func=func, **kwargs)
    
    return wrapper
