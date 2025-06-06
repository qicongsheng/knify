import sys

from knify.apscheduler.executors.base import BaseExecutor, run_job

try:
    import gevent
except ImportError as exc:  # pragma: nocover
    raise ImportError("GeventExecutor requires gevent installed") from exc


class GeventExecutor(BaseExecutor):
    """
    Runs jobs as greenlets.

    Plugin alias: ``gevent``
    """

    def _do_submit_job(self, job, run_times):
        def callback(greenlet):
            try:
                events = greenlet.get()
            except BaseException:
                self._run_job_error(job.id, *sys.exc_info()[1:])
            else:
                self._run_job_success(job.id, events)

        gevent.spawn(
            run_job, job, job._jobstore_alias, run_times, self._logger.name
        ).link(callback)
