from knify.apscheduler.schedulers.base import BaseScheduler
from knify.apscheduler.schedulers.blocking import BlockingScheduler

try:
    import gevent
    from gevent.event import Event
    from gevent.lock import RLock
except ImportError as exc:  # pragma: nocover
    raise ImportError("GeventScheduler requires gevent installed") from exc


class GeventScheduler(BlockingScheduler):
    """A scheduler that runs as a Gevent greenlet."""

    _greenlet = None

    def start(self, *args, **kwargs):
        self._event = Event()
        BaseScheduler.start(self, *args, **kwargs)
        self._greenlet = gevent.spawn(self._main_loop)
        return self._greenlet

    def shutdown(self, *args, **kwargs):
        super().shutdown(*args, **kwargs)
        self._greenlet.join()
        del self._greenlet

    def _create_lock(self):
        return RLock()

    def _create_default_executor(self):
        from knify.apscheduler.executors.gevent import GeventExecutor

        return GeventExecutor()
