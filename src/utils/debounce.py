from functools import wraps
from typing import Callable, Optional, Any
from PySide6.QtCore import QTimer, QObject, Signal

class Debounce(QObject):
    """
    Debouncer that delays execution of the function until after `delay_ms`
    milliseconds have elapsed since the last time the function was invoked.
    """
    timeout = Signal(object)

    def __init__(self, delay_ms: int, callback: Optional[Callable] = None):
        super().__init__()
        self.callback = callback
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_ms)
        self.timer.timeout.connect(self._execute)
        self._args = ()
        self._kwargs = {}

    def call(self, *args, **kwargs):
        self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.timer.start()

    def _execute(self):
        val = self._args[0] if self._args else None
        self.timeout.emit(val)
        if self.callback:
            self.callback(*self._args, **self._kwargs)

class Throttle(QObject):
    """
    Throttler that limits execution of the function to at most once per `interval_ms`.
    Uses trailing edge (executes the most recent call after the interval).
    """
    timeout = Signal(object)

    def __init__(self, interval_ms: int, callback: Optional[Callable] = None):
        super().__init__()
        self.interval_ms = interval_ms
        self.callback = callback
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timeout)
        self._pending = False
        self._args = ()
        self._kwargs = {}

    def call(self, *args, **kwargs):
        self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        if not self.timer.isActive():
            self._execute()
            self.timer.start(self.interval_ms)
        else:
            self._pending = True

    def _execute(self):
        val = self._args[0] if self._args else None
        self.timeout.emit(val)
        if self.callback:
            self.callback(*self._args, **self._kwargs)

    def _on_timeout(self):
        if self._pending:
            self._execute()
            self._pending = False
            self.timer.start(self.interval_ms)

def debounce(delay_ms: int):
    """Decorator to debounce a function call."""
    def decorator(func: Callable):
        debouncer = Debounce(delay_ms, func)
        @wraps(func)
        def wrapper(*args, **kwargs):
            debouncer(*args, **kwargs)
        return wrapper
    return decorator

def throttle(interval_ms: int):
    """Decorator to throttle a function call."""
    def decorator(func: Callable):
        throttler = Throttle(interval_ms, func)
        @wraps(func)
        def wrapper(*args, **kwargs):
            throttler(*args, **kwargs)
        return wrapper
    return decorator
