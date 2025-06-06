import sys

from knify.apscheduler.executors.base import BaseExecutor, run_coroutine_job, run_job
from knify.apscheduler.util import iscoroutinefunction_partial


class AsyncIOExecutor(BaseExecutor):
    """
    Runs jobs in the default executor of the event loop.

    If the job function is a native coroutine function, it is scheduled to be run directly in the
    event loop as soon as possible. All other functions are run in the event loop's default
    executor which is usually a thread pool.

    Plugin alias: ``asyncio``
    """

    def start(self, scheduler, alias):
        super().start(scheduler, alias)
        self._eventloop = scheduler._eventloop
        self._pending_futures = set()

    def shutdown(self, wait=True):
        # There is no way to honor wait=True without converting this method into a coroutine method
        for f in self._pending_futures:
            if not f.done():
                f.cancel()

        self._pending_futures.clear()

    def _do_submit_job(self, job, run_times):
        def callback(f):
            self._pending_futures.discard(f)
            try:
                events = f.result()
            except BaseException:
                self._run_job_error(job.id, *sys.exc_info()[1:])
            else:
                self._run_job_success(job.id, events)

        if iscoroutinefunction_partial(job.func):
            coro = run_coroutine_job(
                job, job._jobstore_alias, run_times, self._logger.name
            )
            f = self._eventloop.create_task(coro)
        else:
            f = self._eventloop.run_in_executor(
                None, run_job, job, job._jobstore_alias, run_times, self._logger.name
            )

        f.add_done_callback(callback)
        self._pending_futures.add(f)
