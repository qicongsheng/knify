from threading import Event, Thread

from knify.apscheduler.schedulers.base import BaseScheduler
from knify.apscheduler.schedulers.blocking import BlockingScheduler
from knify.apscheduler.util import asbool


class BackgroundScheduler(BlockingScheduler):
    """
    A scheduler that runs in the background using a separate thread
    (:meth:`~apscheduler.schedulers.base.BaseScheduler.start` will return immediately).

    Extra options:

    ========== =============================================================================
    ``daemon`` Set the ``daemon`` option in the background thread (defaults to ``True``, see
               `the documentation
               <https://docs.python.org/3.4/library/threading.html#thread-objects>`_
               for further details)
    ========== =============================================================================
    """

    _thread = None

    def _configure(self, config):
        self._daemon = asbool(config.pop("daemon", True))
        super()._configure(config)

    def start(self, *args, **kwargs):
        if self._event is None or self._event.is_set():
            self._event = Event()

        BaseScheduler.start(self, *args, **kwargs)
        self._thread = Thread(
            target=self._main_loop, name="APScheduler", daemon=self._daemon
        )
        self._thread.start()

    def shutdown(self, *args, **kwargs):
        super().shutdown(*args, **kwargs)
        self._thread.join()
        del self._thread
