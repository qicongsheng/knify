import sys
from concurrent.futures import ThreadPoolExecutor

from tornado.gen import convert_yielded

from knify.apscheduler.executors.base import BaseExecutor, run_coroutine_job, run_job
from knify.apscheduler.util import iscoroutinefunction_partial


class TornadoExecutor(BaseExecutor):
    """
    Runs jobs either in a thread pool or directly on the I/O loop.

    If the job function is a native coroutine function, it is scheduled to be run directly in the
    I/O loop as soon as possible. All other functions are run in a thread pool.

    Plugin alias: ``tornado``

    :param int max_workers: maximum number of worker threads in the thread pool
    """

    def __init__(self, max_workers=10):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers)

    def start(self, scheduler, alias):
        super().start(scheduler, alias)
        self._ioloop = scheduler._ioloop

    def _do_submit_job(self, job, run_times):
        def callback(f):
            try:
                events = f.result()
            except BaseException:
                self._run_job_error(job.id, *sys.exc_info()[1:])
            else:
                self._run_job_success(job.id, events)

        if iscoroutinefunction_partial(job.func):
            f = run_coroutine_job(
                job, job._jobstore_alias, run_times, self._logger.name
            )
        else:
            f = self.executor.submit(
                run_job, job, job._jobstore_alias, run_times, self._logger.name
            )

        f = convert_yielded(f)
        f.add_done_callback(callback)
