from importlib import import_module
from itertools import product

from knify.apscheduler.schedulers.base import BaseScheduler

for version, pkgname in product(range(6, 1, -1), ("PySide", "PyQt")):
    try:
        qtcore = import_module(pkgname + str(version) + ".QtCore")
    except ImportError:
        pass
    else:
        QTimer = qtcore.QTimer
        break
else:
    raise ImportError("QtScheduler requires either PySide/PyQt (v6 to v2) installed")


class QtScheduler(BaseScheduler):
    """A scheduler that runs in a Qt event loop."""

    _timer = None

    def shutdown(self, *args, **kwargs):
        super().shutdown(*args, **kwargs)
        self._stop_timer()

    def _start_timer(self, wait_seconds):
        self._stop_timer()
        if wait_seconds is not None:
            wait_time = min(int(wait_seconds * 1000), 2147483647)
            self._timer = QTimer.singleShot(wait_time, self._process_jobs)

    def _stop_timer(self):
        if self._timer:
            if self._timer.isActive():
                self._timer.stop()
            del self._timer

    def wakeup(self):
        self._start_timer(0)

    def _process_jobs(self):
        wait_seconds = super()._process_jobs()
        self._start_timer(wait_seconds)
