# Desync

Simple conversions between synchronous and asynchronous functions and function
calls. You can use it to wait (really block) for asynchronous function results
with `sync` or create synchronous versions with `synced`:

```python
    # Assume async_func is asynchronous.
    async_func: Callable[..., Awaitable[T]]

    # Call async_func and wait for its result synchronously:
    result: T = sync(async_func, *args, **kwargs)

    # Create a version which is synchronous without calling it:
    desynced_func: Callable[..., T] = synced(async_func)
```

You can also wait for synchronous functions via `desync` or create asynchronous
versions with `desynced`:

```python
    # Assume sync_func is synchronous.
    func: Callable[..., T]

    # Call sync_func and wait for its result in an asynchronous context:
    awaitable: Awaitable[T] = desync(sync_func, *args, **kwargs)
    result: T = await awaitable

    # Create a version which is asynchronous without calling it:
    descyned_func: Callable[..., Awaitable[T]] = desynced(func)
```

Desynced functions run in parallel (as far as python can run in parallel). 

```python
    def wait_some():
        time.sleep(1)
        return 1

    # This should take approx. 1 second:
    assert 10 == sum(
        await asyncio.gather(*(
            desync(wait_some) for i in range(10)
        ))
    )
```