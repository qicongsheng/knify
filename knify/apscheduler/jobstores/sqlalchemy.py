import pickle

from knify.apscheduler.job import Job
from knify.apscheduler.jobstores.base import BaseJobStore, ConflictingIdError, JobLookupError
from knify.apscheduler.util import (
    datetime_to_utc_timestamp,
    maybe_ref,
    utc_timestamp_to_datetime,
)

try:
    from sqlalchemy import (
        Column,
        Float,
        LargeBinary,
        MetaData,
        Table,
        Unicode,
        and_,
        create_engine,
        select,
    )
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.sql.expression import null
except ImportError as exc:  # pragma: nocover
    raise ImportError("SQLAlchemyJobStore requires SQLAlchemy installed") from exc


class SQLAlchemyJobStore(BaseJobStore):
    """
    Stores jobs in a database table using SQLAlchemy.
    The table will be created if it doesn't exist in the database.

    Plugin alias: ``sqlalchemy``

    :param str url: connection string (see
        :ref:`SQLAlchemy documentation <sqlalchemy:database_urls>` on this)
    :param engine: an SQLAlchemy :class:`~sqlalchemy.engine.Engine` to use instead of creating a
        new one based on ``url``
    :param str tablename: name of the table to store jobs in
    :param metadata: a :class:`~sqlalchemy.schema.MetaData` instance to use instead of creating a
        new one
    :param int pickle_protocol: pickle protocol level to use (for serialization), defaults to the
        highest available
    :param str tableschema: name of the (existing) schema in the target database where the table
        should be
    :param dict engine_options: keyword arguments to :func:`~sqlalchemy.create_engine`
        (ignored if ``engine`` is given)
    """

    def __init__(
        self,
        url=None,
        engine=None,
        tablename="apscheduler_jobs",
        metadata=None,
        pickle_protocol=pickle.HIGHEST_PROTOCOL,
        tableschema=None,
        engine_options=None,
    ):
        super().__init__()
        self.pickle_protocol = pickle_protocol
        metadata = maybe_ref(metadata) or MetaData()

        if engine:
            self.engine = maybe_ref(engine)
        elif url:
            self.engine = create_engine(url, **(engine_options or {}))
        else:
            raise ValueError('Need either "engine" or "url" defined')

        # 191 = max key length in MySQL for InnoDB/utf8mb4 tables,
        # 25 = precision that translates to an 8-byte float
        self.jobs_t = Table(
            tablename,
            metadata,
            Column("id", Unicode(191), primary_key=True),
            Column("next_run_time", Float(25), index=True),
            Column("job_state", LargeBinary, nullable=False),
            schema=tableschema,
        )

    def start(self, scheduler, alias):
        super().start(scheduler, alias)
        self.jobs_t.create(self.engine, True)

    def lookup_job(self, job_id):
        selectable = select(self.jobs_t.c.job_state).where(self.jobs_t.c.id == job_id)
        with self.engine.begin() as connection:
            job_state = connection.execute(selectable).scalar()
            return self._reconstitute_job(job_state) if job_state else None

    def get_due_jobs(self, now):
        timestamp = datetime_to_utc_timestamp(now)
        return self._get_jobs(self.jobs_t.c.next_run_time <= timestamp)

    def get_next_run_time(self):
        selectable = (
            select(self.jobs_t.c.next_run_time)
            .where(self.jobs_t.c.next_run_time != null())
            .order_by(self.jobs_t.c.next_run_time)
            .limit(1)
        )
        with self.engine.begin() as connection:
            next_run_time = connection.execute(selectable).scalar()
            return utc_timestamp_to_datetime(next_run_time)

    def get_all_jobs(self):
        jobs = self._get_jobs()
        self._fix_paused_jobs_sorting(jobs)
        return jobs

    def add_job(self, job):
        insert = self.jobs_t.insert().values(
            **{
                "id": job.id,
                "next_run_time": datetime_to_utc_timestamp(job.next_run_time),
                "job_state": pickle.dumps(job.__getstate__(), self.pickle_protocol),
            }
        )
        with self.engine.begin() as connection:
            try:
                connection.execute(insert)
            except IntegrityError:
                raise ConflictingIdError(job.id)

    def update_job(self, job):
        update = (
            self.jobs_t.update()
            .values(
                **{
                    "next_run_time": datetime_to_utc_timestamp(job.next_run_time),
                    "job_state": pickle.dumps(job.__getstate__(), self.pickle_protocol),
                }
            )
            .where(self.jobs_t.c.id == job.id)
        )
        with self.engine.begin() as connection:
            result = connection.execute(update)
            if result.rowcount == 0:
                raise JobLookupError(job.id)

    def remove_job(self, job_id):
        delete = self.jobs_t.delete().where(self.jobs_t.c.id == job_id)
        with self.engine.begin() as connection:
            result = connection.execute(delete)
            if result.rowcount == 0:
                raise JobLookupError(job_id)

    def remove_all_jobs(self):
        delete = self.jobs_t.delete()
        with self.engine.begin() as connection:
            connection.execute(delete)

    def shutdown(self):
        self.engine.dispose()

    def _reconstitute_job(self, job_state):
        job_state = pickle.loads(job_state)
        job_state["jobstore"] = self
        job = Job.__new__(Job)
        job.__setstate__(job_state)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job

    def _get_jobs(self, *conditions):
        jobs = []
        selectable = select(self.jobs_t.c.id, self.jobs_t.c.job_state).order_by(
            self.jobs_t.c.next_run_time
        )
        selectable = selectable.where(and_(*conditions)) if conditions else selectable
        failed_job_ids = set()
        with self.engine.begin() as connection:
            for row in connection.execute(selectable):
                try:
                    jobs.append(self._reconstitute_job(row.job_state))
                except BaseException:
                    self._logger.exception(
                        'Unable to restore job "%s" -- removing it', row.id
                    )
                    failed_job_ids.add(row.id)

            # Remove all the jobs we failed to restore
            if failed_job_ids:
                delete = self.jobs_t.delete().where(
                    self.jobs_t.c.id.in_(failed_job_ids)
                )
                connection.execute(delete)

        return jobs

    def __repr__(self):
        return f"<{self.__class__.__name__} (url={self.engine.url})>"
