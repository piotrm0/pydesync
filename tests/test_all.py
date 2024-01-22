import asyncio
import functools
import time
from datetime import datetime

import pytest

from pydesync import desync, desynced, sync, synced


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

    # python 3.10 requires this order of decorators.
    @staticmethod
    @functools.wraps(_async_sleep_some_and_return_negation)
    async def _async_sleep_some_and_return_negation_wrapper(*args, **kwargs):
        """
        Wrapper of the above.
        """

        return await Tests._async_sleep_some_and_return_negation(*args, **kwargs)

    @staticmethod
    def _sleep_some_and_return_negation(i: int):
        """
        Function that blocks for `SHORT_TIME` seconds before returning the
        negation of its integer input.
        """

        time.sleep(Tests.SHORT_TIME)
        return -i

    # python 3.10 requires this order of decorators.
    @staticmethod
    @functools.wraps(_sleep_some_and_return_negation)
    def _sleep_some_and_return_negation_wrapper(*args, **kwargs):
        """
        Wrapper of the above.
        """

        return Tests._sleep_some_and_return_negation(*args, **kwargs)

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
        await self._test_async(Tests._async_sleep_some_and_return_negation_wrapper)
        
        self._test_sync(Tests._sleep_some_and_return_negation)
        self._test_sync(Tests._sleep_some_and_return_negation_wrapper)

    def test_sync(self):
        """
        Test a `sync` on an asynchronous sleeper. Checks that it produces
        the expected results only.
        """
        self._test_sync(
            lambda i:
            sync(Tests._async_sleep_some_and_return_negation, i=i)
        )

    def test_sync_wrapped(self):
        """
        Test a `sync` on a wrapper.
        """
        self._test_sync(
            lambda i:
            sync(Tests._async_sleep_some_and_return_negation_wrapper, i=i)
        )

    def test_synced(self):
        """
        Test `synced` on an asynchronous sleeper. Checks that it produces
        the expected results only.
        """
        self._test_sync(
            synced(Tests._async_sleep_some_and_return_negation)
        )

    def test_synced_wrapped(self):
        """
        Test `synced` on a wrapper.
        """
        self._test_sync(
            synced(Tests._async_sleep_some_and_return_negation_wrapper)
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
    async def test_desync_wrapped(self):
        """
        Test `desync` on a wrapper.
        """

        await self._test_async(
            lambda i: desync(Tests._sleep_some_and_return_negation_wrapper, i=i)
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
    async def test_desynced_wrapped(self):
        """
        Test `desynced` on a wrapper.
        """

        await self._test_async(
            desynced(Tests._sleep_some_and_return_negation_wrapper)
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
