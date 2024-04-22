import threading

from functools import wraps

__all__ = ["locks"]

# A default lock for the event system
_lock = threading.RLock()


def locks(lock=None):
    """DECORATOR: The decorated function locks its thread during execution.

    The given lock is acquired by the current thread before the function is
    executed, and releases it upon completion.

    Args:
        lock: A lock object with an acquire and release method.  If no lock
            is provided, a re-entrant lock (threading.RLock) will be used.

    example:

        @locks()
        def my_function():
            function_that_changes_some_state()

    """
    lock = lock or _lock

    def decorated(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)

        return wrapped

    return decorated
