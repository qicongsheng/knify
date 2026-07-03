#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
"""
轻量级任务调度系统（单文件实现，对应设计文档 V2.0）

核心语义（与设计文档一一对应）：
- D1 Cron：支持 5 位（分 时 日 月 周）与 6 位（秒 分 时 日 月 周），按字段数自动识别
- D2 超时：线程执行器为「软超时」（停止等待 + 释放逻辑槽位，后台线程不保证回收）；
          异步执行器为「硬取消」（asyncio.wait_for 真实 cancel）
- D3 路由：按函数类型自动路由，同步函数进线程池，async def 进事件循环
- D4 并发：max_instances 为准入控制，准入即占「逻辑槽位」（running_count++）；
          max_workers 为全局硬上限
- D5 状态：状态属于「实例」，任务只持聚合计数
- D6 超时算失败：超时纳入重试；重试耗尽后终态为 TIMEOUT 或 FAILED
- D7 重试非阻塞：失败释放 worker，按 retry_delay 延迟由主循环重投，逻辑槽位保持占用
- D8 阻塞超时：主循环独立清扫 WAIT 队列超时项，不依赖运行实例完成
- D9 线程安全：每个任务一把 RLock 保护 running_count / 队列 / 状态

仅依赖：croniter、pytz
"""
import asyncio
import json
import logging
import signal
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future, CancelledError as FutureCancelledError
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from croniter import croniter
import pytz

from knify import logger

# --------------------------------------------------------------------------- #
# 日志：复用项目的 knify.logger（loguru 封装）
# 仍用标准库的日志级别常量做分派，映射到 logger 的 info/warn/error
# --------------------------------------------------------------------------- #
_LEVEL_FUNC = {
    logging.DEBUG: logger.debug,
    logging.INFO: logger.info,
    logging.WARNING: logger.warn,
    logging.ERROR: logger.error,
}


def _emit(level: int, msg: str):
    _LEVEL_FUNC.get(level, logger.info)(msg)


# --------------------------------------------------------------------------- #
# 枚举
# --------------------------------------------------------------------------- #
class BlockingStrategy(str, Enum):
    WAIT = "WAIT"
    DROP = "DROP"
    RAISE = "RAISE"


class InstanceState(str, Enum):
    BLOCKED = "BLOCKED"              # 并发满，在 WAIT 队列等待
    PENDING_RETRY = "PENDING_RETRY"  # 上次失败，等待 retry_delay 后重试
    RUNNING = "RUNNING"             # 正在执行（含线程池排队）
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TriggerSource(str, Enum):
    CRON = "cron"
    IMMEDIATE = "immediate"
    MANUAL = "manual"


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class SchedulerError(Exception):
    pass


class TaskNotFoundError(SchedulerError):
    pass


class TaskAlreadyExistsError(SchedulerError):
    pass


class InvalidCronExpressionError(SchedulerError):
    pass


class MaxInstancesReachedError(SchedulerError):
    pass


class TaskTimeoutError(SchedulerError):
    pass


class TaskExecutionError(SchedulerError):
    pass


# --------------------------------------------------------------------------- #
# 实例
# --------------------------------------------------------------------------- #
@dataclass
class Instance:
    instance_id: str
    task_id: str
    args: List[Any]
    kwargs: Dict[str, Any]
    source: str
    is_async: bool
    attempt: int = 1
    state: InstanceState = InstanceState.RUNNING
    finalized: bool = False
    future: Optional[Future] = None
    enqueue_at: float = 0.0          # 进入 WAIT 队列的时刻
    attempt_start: float = 0.0       # 本次尝试开始执行的时刻
    timeout_at: Optional[float] = None
    next_retry_at: float = 0.0


# --------------------------------------------------------------------------- #
# 任务
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    task_id: str
    func: Callable
    cron: str
    is_coroutine: bool
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    max_instances: int = 1
    blocking_strategy: BlockingStrategy = BlockingStrategy.WAIT
    blocking_timeout: int = 300
    max_queue_size: int = 100
    retry_times: int = 0
    retry_delay: int = 60
    timeout: Optional[int] = None
    name: Optional[str] = None

    enabled: bool = True
    next_run: Optional[datetime] = None
    running_count: int = 0
    blocked_queue: deque = field(default_factory=deque)
    instances: Dict[str, Instance] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)
    _seq: int = 0
    _pending_immediate: bool = False

    # 统计
    last_run_time: Optional[str] = None
    last_status: Optional[str] = None
    last_trigger_source: Optional[str] = None
    success_count: int = 0
    failed_count: int = 0
    total_triggered: int = 0


# --------------------------------------------------------------------------- #
# 调度器
# --------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self,
                 timezone: str = "Asia/Shanghai",
                 max_workers: int = 10,
                 default_max_instances: int = 1,
                 default_blocking_strategy: str = "WAIT",
                 default_blocking_timeout: int = 300,
                 tick_interval: float = 1.0):
        self._tz = pytz.timezone(timezone)
        self._max_workers = max_workers
        self._default_max_instances = default_max_instances
        self._default_blocking_strategy = BlockingStrategy(default_blocking_strategy)
        self._default_blocking_timeout = default_blocking_timeout
        self._tick = tick_interval

        self._jobs: Dict[str, Job] = {}
        self._registry_lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers,
                                        thread_name_prefix="lite-sched")
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------ #
    # 时间辅助
    # ------------------------------------------------------------------ #
    def _now_dt(self) -> datetime:
        return datetime.now(self._tz)

    @staticmethod
    def _make_croniter(expr: str, base: datetime) -> croniter:
        fields = expr.split()
        try:
            if len(fields) == 6:
                return croniter(expr, base, second_at_beginning=True)
            if len(fields) == 5:
                return croniter(expr, base)
        except Exception as e:  # noqa
            raise InvalidCronExpressionError(f"非法 Cron 表达式 '{expr}': {e}")
        raise InvalidCronExpressionError(
            f"非法 Cron 表达式 '{expr}': 仅支持 5 位或 6 位，当前 {len(fields)} 位")

    def _compute_next(self, expr: str, base: datetime) -> datetime:
        return self._make_croniter(expr, base).get_next(datetime)

    # ------------------------------------------------------------------ #
    # 日志
    # ------------------------------------------------------------------ #
    def _log(self, job: Job, inst: Instance, event: str, level: int, **extra):
        record = {
            "timestamp": self._now_dt().strftime("%Y-%m-%d %H:%M:%S"),
            "task_id": job.task_id,
            "instance_id": inst.instance_id,
            "event": event,
            "source": inst.source,
            "attempt": inst.attempt,
            "args": inst.args,
            "kwargs": inst.kwargs,
        }
        for k, v in extra.items():
            if v is not None:
                record[k] = v
        _emit(level, json.dumps(record, ensure_ascii=False, default=str))

    def _log_scheduler(self, event: str, level: int = logging.INFO, **extra):
        record = {"timestamp": self._now_dt().strftime("%Y-%m-%d %H:%M:%S"), "event": event}
        record.update(extra)
        _emit(level, json.dumps(record, ensure_ascii=False, default=str))

    # ------------------------------------------------------------------ #
    # 注册 / 生命周期
    # ------------------------------------------------------------------ #
    def add_job(self,
                task_id: str,
                func: Callable,
                cron: str,
                args: Optional[List] = None,
                kwargs: Optional[Dict] = None,
                run_immediately: bool = False,
                max_instances: Optional[int] = None,
                blocking_strategy: Optional[str] = None,
                blocking_timeout: Optional[int] = None,
                max_queue_size: int = 100,
                retry_times: int = 0,
                retry_delay: int = 60,
                timeout: Optional[int] = None,
                name: Optional[str] = None) -> Job:
        if not callable(func):
            raise SchedulerError("func 必须是可调用对象")
        with self._registry_lock:
            if task_id in self._jobs:
                raise TaskAlreadyExistsError(f"任务已存在: {task_id}")
            # 校验 cron（会在非法时抛 InvalidCronExpressionError）
            first_next = self._compute_next(cron, self._now_dt())

            job = Job(
                task_id=task_id,
                func=func,
                cron=cron,
                is_coroutine=asyncio.iscoroutinefunction(func),
                args=list(args) if args else [],
                kwargs=dict(kwargs) if kwargs else {},
                max_instances=max_instances if max_instances is not None else self._default_max_instances,
                blocking_strategy=BlockingStrategy(blocking_strategy) if blocking_strategy
                else self._default_blocking_strategy,
                blocking_timeout=blocking_timeout if blocking_timeout is not None
                else self._default_blocking_timeout,
                max_queue_size=max_queue_size,
                retry_times=retry_times,
                retry_delay=retry_delay,
                timeout=timeout,
                name=name,
                next_run=first_next,
            )
            self._jobs[task_id] = job

        self._log_scheduler("job_added", task_id=task_id, cron=cron,
                            max_instances=job.max_instances,
                            strategy=job.blocking_strategy.value,
                            is_async=job.is_coroutine)

        if run_immediately:
            if self._running:
                self._submit(job, TriggerSource.IMMEDIATE)
            else:
                job._pending_immediate = True
        return job


    def task(self, task_id: str, cron: str, **opts):
        """装饰器注册。"""
        def decorator(fn: Callable) -> Callable:
            self.add_job(task_id=task_id, func=fn, cron=cron, **opts)
            return fn
        return decorator

    def _get_job(self, task_id: str) -> Job:
        job = self._jobs.get(task_id)
        if job is None:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        return job

    def remove_job(self, task_id: str):
        with self._registry_lock:
            job = self._jobs.pop(task_id, None)
        if job is None:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        with job.lock:
            job.enabled = False
            self._drain_queue(job, InstanceState.CANCELLED, "任务被移除")
        # RUNNING 实例不强杀，其回调仍会正常收尾（不再影响调度）
        self._log_scheduler("job_removed", task_id=task_id)

    def pause_job(self, task_id: str):
        job = self._get_job(task_id)
        with job.lock:
            job.enabled = False
        self._log_scheduler("job_paused", task_id=task_id)

    def resume_job(self, task_id: str):
        job = self._get_job(task_id)
        with job.lock:
            job.enabled = True
            job.next_run = self._compute_next(job.cron, self._now_dt())
        self._log_scheduler("job_resumed", task_id=task_id)

    def update_job_params(self, task_id: str,
                          args: Optional[List] = None,
                          kwargs: Optional[Dict] = None):
        """仅影响此后新产生的触发；已存在实例保留各自的参数快照。"""
        job = self._get_job(task_id)
        with job.lock:
            if args is not None:
                job.args = list(args)
            if kwargs is not None:
                job.kwargs = dict(kwargs)
        self._log_scheduler("job_params_updated", task_id=task_id,
                            args=job.args, kwargs=job.kwargs)

    def trigger_job(self, task_id: str) -> Optional[str]:
        """手动触发一次；RAISE 策略且并发满时抛 MaxInstancesReachedError。"""
        job = self._get_job(task_id)
        inst = self._submit(job, TriggerSource.MANUAL)
        return inst.instance_id if inst else None

    def clear_blocked_queue(self, task_id: str):
        job = self._get_job(task_id)
        with job.lock:
            self._drain_queue(job, InstanceState.CANCELLED, "阻塞队列被清理")

    def get_blocked_jobs(self) -> Dict[str, List[str]]:
        result = {}
        for job in list(self._jobs.values()):
            with job.lock:
                if job.blocked_queue:
                    result[job.task_id] = [i.instance_id for i in job.blocked_queue]
        return result

    def get_job_status(self, task_id: str) -> Dict[str, Any]:
        job = self._get_job(task_id)
        with job.lock:
            return {
                "task_id": job.task_id,
                "name": job.name,
                "enabled": job.enabled,
                "max_instances": job.max_instances,
                "running_instances": job.running_count,
                "blocked_queue_size": len(job.blocked_queue),
                "next_run_time": job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else None,
                "last_run_time": job.last_run_time,
                "last_status": job.last_status,
                "success_count": job.success_count,
                "failed_count": job.failed_count,
                "total_triggered": job.total_triggered,
                "args": list(job.args),
                "kwargs": dict(job.kwargs),
                "blocking_strategy": job.blocking_strategy.value,
                "last_trigger_source": job.last_trigger_source,
            }

    # ------------------------------------------------------------------ #
    # 提交与准入（§6.2）
    # ------------------------------------------------------------------ #
    def _new_instance(self, job: Job, source: TriggerSource) -> Instance:
        job._seq += 1
        inst = Instance(
            instance_id=f"{job.task_id}#{job._seq}",
            task_id=job.task_id,
            args=list(job.args),      # 触发时刻的参数快照
            kwargs=dict(job.kwargs),
            source=source.value,
            is_async=job.is_coroutine,
        )
        job.instances[inst.instance_id] = inst
        return inst

    def _submit(self, job: Job, source: TriggerSource) -> Optional[Instance]:
        with job.lock:
            job.total_triggered += 1
            job.last_trigger_source = source.value

            if job.running_count < job.max_instances:
                job.running_count += 1
                inst = self._new_instance(job, source)
                self._dispatch(job, inst)
                return inst

            # 并发已满，执行阻塞策略
            strat = job.blocking_strategy
            if strat == BlockingStrategy.DROP:
                inst = self._new_instance(job, source)
                self._reject(job, inst, "max_instances 已满 (DROP)")
                return None

            if strat == BlockingStrategy.RAISE:
                if source == TriggerSource.MANUAL:
                    raise MaxInstancesReachedError(
                        f"任务 {job.task_id} 并发已满 (max_instances={job.max_instances})")
                # 自动触发无调用方接异常 → 降级为 DROP（明确记录）
                inst = self._new_instance(job, source)
                self._reject(job, inst, "RAISE 对自动触发降级为 DROP")
                return None

            # WAIT
            if len(job.blocked_queue) >= job.max_queue_size:
                inst = self._new_instance(job, source)
                self._reject(job, inst, f"WAIT 队列已满 (max_queue_size={job.max_queue_size})")
                return None
            inst = self._new_instance(job, source)
            inst.state = InstanceState.BLOCKED
            inst.enqueue_at = time.time()
            job.blocked_queue.append(inst)
            self._log(job, inst, "blocked", logging.INFO)
            return inst

    def _reject(self, job: Job, inst: Instance, reason: str):
        inst.finalized = True
        inst.state = InstanceState.REJECTED
        job.last_status = InstanceState.REJECTED.value
        job.instances.pop(inst.instance_id, None)
        self._log(job, inst, "rejected", logging.WARNING, error=reason)

    def _drain_queue(self, job: Job, state: InstanceState, reason: str):
        """把 WAIT 队列全部出队并置为指定终态（调用方须持 job.lock）。"""
        while job.blocked_queue:
            inst = job.blocked_queue.popleft()
            inst.finalized = True
            inst.state = state
            job.instances.pop(inst.instance_id, None)
            self._log(job, inst, state.value.lower(), logging.WARNING, error=reason)

    # ------------------------------------------------------------------ #
    # 分发执行（§6.3）
    # ------------------------------------------------------------------ #
    def _dispatch(self, job: Job, inst: Instance):
        """把实例投递到执行器（调用方须持 job.lock）。首投与重投共用。"""
        inst.state = InstanceState.RUNNING
        inst.attempt_start = time.time()
        inst.timeout_at = (inst.attempt_start + job.timeout) if job.timeout else None
        job.last_run_time = self._now_dt().strftime("%Y-%m-%d %H:%M:%S")

        if inst.is_async:
            if self._loop is None:
                raise SchedulerError("异步任务需要先调用 start() 启动事件循环")
            coro = job.func(*inst.args, **inst.kwargs)
            if job.timeout:
                coro = asyncio.wait_for(coro, job.timeout)
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            fut = self._pool.submit(job.func, *inst.args, **inst.kwargs)

        inst.future = fut
        fut.add_done_callback(
            lambda f, j=job, i=inst: self._on_future_done(j, i, f))
        self._log(job, inst, "start", logging.INFO)

    def _on_future_done(self, job: Job, inst: Instance, fut: Future):
        # 陈旧回调（软超时后已重投产生新 future）直接忽略
        if inst.future is not fut:
            return
        try:
            fut.result()
            self._handle_attempt_result(job, inst, success=True, timed_out=False, error=None)
        except (asyncio.TimeoutError,) as e:
            self._handle_attempt_result(job, inst, success=False, timed_out=True,
                                        error=TaskTimeoutError(str(e) or "timeout"))
        except (FutureCancelledError, asyncio.CancelledError):
            self._handle_attempt_result(job, inst, success=False, timed_out=True,
                                        error=TaskTimeoutError("cancelled"))
        except Exception as e:  # noqa - 业务异常隔离
            self._handle_attempt_result(job, inst, success=False, timed_out=False,
                                        error=TaskExecutionError(repr(e)))

    def _handle_attempt_result(self, job: Job, inst: Instance,
                               success: bool, timed_out: bool, error):
        duration_ms = int((time.time() - inst.attempt_start) * 1000)
        with job.lock:
            # 已终结 / 已不在运行态（软超时与真实完成竞态） → 忽略
            if inst.finalized or inst.state != InstanceState.RUNNING:
                return

            if success:
                inst.finalized = True
                inst.state = InstanceState.SUCCESS
                job.success_count += 1
                job.last_status = InstanceState.SUCCESS.value
                self._log(job, inst, "success", logging.INFO, duration_ms=duration_ms)
                self._release_slot(job, inst)
                return

            # 失败 / 超时：判断是否还可重试（D6 超时纳入重试）
            if inst.attempt <= job.retry_times:
                inst.attempt += 1
                inst.state = InstanceState.PENDING_RETRY
                inst.next_retry_at = time.time() + job.retry_delay
                # D7：保持逻辑槽位占用，释放 worker；由主循环延迟重投
                self._log(job, inst, "retry", logging.WARNING,
                          error=str(error), duration_ms=duration_ms)
            else:
                inst.finalized = True
                inst.state = InstanceState.TIMEOUT if timed_out else InstanceState.FAILED
                job.failed_count += 1
                job.last_status = inst.state.value
                self._log(job, inst, "timeout" if timed_out else "failed",
                          logging.ERROR, error=str(error), duration_ms=duration_ms)
                self._release_slot(job, inst)

    def _release_slot(self, job: Job, inst: Instance):
        """释放逻辑槽位并尝试唤醒队列（调用方须持 job.lock）。"""
        job.running_count -= 1
        job.instances.pop(inst.instance_id, None)
        self._wake_next(job)

    def _wake_next(self, job: Job):
        """有空槽位时从 WAIT 队首取实例执行，过期项跳过（调用方须持 job.lock）。"""
        now = time.time()
        while job.running_count < job.max_instances and job.blocked_queue:
            inst = job.blocked_queue.popleft()
            if now - inst.enqueue_at > job.blocking_timeout:
                self._reject(job, inst, "blocking_timeout 等待超时")
                continue
            job.running_count += 1
            self._dispatch(job, inst)

    # ------------------------------------------------------------------ #
    # 主循环清扫（§6.1）
    # ------------------------------------------------------------------ #
    def _sweep_blocked_timeout(self, job: Job, now: float):
        """D8：独立清扫 WAIT 队列超时项，不依赖运行实例完成。"""
        with job.lock:
            if not job.blocked_queue:
                return
            kept = deque()
            while job.blocked_queue:
                inst = job.blocked_queue.popleft()
                if now - inst.enqueue_at > job.blocking_timeout:
                    self._reject(job, inst, "blocking_timeout 等待超时")
                else:
                    kept.append(inst)
            job.blocked_queue = kept

    def _sweep_sync_timeout(self, job: Job, now: float):
        """线程执行器软超时：到期停止等待、释放槽位（后台线程不保证回收）。"""
        with job.lock:
            for inst in list(job.instances.values()):
                if (not inst.is_async and inst.state == InstanceState.RUNNING
                        and inst.timeout_at is not None and now > inst.timeout_at
                        and not inst.finalized):
                    self._handle_attempt_result(
                        job, inst, success=False, timed_out=True,
                        error=TaskTimeoutError(f"软超时 (timeout={job.timeout}s)"))

    def _submit_due_retries(self, job: Job, now: float):
        """D7：重试到期后重新投递。"""
        with job.lock:
            for inst in list(job.instances.values()):
                if inst.state == InstanceState.PENDING_RETRY and now >= inst.next_retry_at:
                    self._dispatch(job, inst)

    def _tick_job(self, job: Job, now_dt: datetime, now_ts: float):
        self._sweep_blocked_timeout(job, now_ts)
        self._sweep_sync_timeout(job, now_ts)
        self._submit_due_retries(job, now_ts)
        if job.enabled and job.next_run is not None and now_dt >= job.next_run:
            self._submit(job, TriggerSource.CRON)
            with job.lock:
                # 推进到严格未来（错失的中间触发被合并）
                job.next_run = self._compute_next(job.cron, now_dt)

    # ------------------------------------------------------------------ #
    # 启停（§3.8）
    # ------------------------------------------------------------------ #
    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _install_signal_handlers(self):
        """尽力注册信号；Windows 仅 SIGINT 可靠，SIGTERM 可能不支持。"""
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            signal.signal(signal.SIGINT, lambda *_: self.shutdown(wait=True))
        except (ValueError, OSError):
            pass
        if hasattr(signal, "SIGTERM"):
            try:
                signal.signal(signal.SIGTERM, lambda *_: self.shutdown(wait=True))
            except (ValueError, OSError):
                pass

    def start(self, block: bool = True):
        if self._running:
            return
        self._running = True

        # 启动异步事件循环线程（承载 async 任务）
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_event_loop, name="lite-sched-loop", daemon=True)
        self._loop_thread.start()

        # 容量提示（D4）
        total_slots = sum(j.max_instances for j in self._jobs.values()
                          if not j.is_coroutine)
        if total_slots > self._max_workers:
            self._log_scheduler("capacity_warning", level=logging.WARNING,
                                sum_max_instances=total_slots,
                                max_workers=self._max_workers,
                                message="同步任务槽位总和超过 max_workers，可能产生线程池排队延迟")

        # 触发 run_immediately（在事件循环就绪后）
        for job in list(self._jobs.values()):
            if job._pending_immediate:
                job._pending_immediate = False
                self._submit(job, TriggerSource.IMMEDIATE)

        self._install_signal_handlers()
        self._log_scheduler("scheduler_started", job_count=len(self._jobs))

        if not block:
            threading.Thread(target=self._main_loop, name="lite-sched-main",
                             daemon=True).start()
        else:
            self._main_loop()

    def _main_loop(self):
        try:
            while self._running:
                now_dt = self._now_dt()
                now_ts = time.time()
                for job in list(self._jobs.values()):
                    try:
                        self._tick_job(job, now_dt, now_ts)
                    except Exception as e:  # noqa - 单任务异常不影响主循环
                        self._log_scheduler("tick_error", level=logging.ERROR,
                                            task_id=job.task_id, error=repr(e))
                time.sleep(self._tick)
        except KeyboardInterrupt:
            self.shutdown(wait=True)

    def shutdown(self, wait: bool = True, timeout: int = 30):
        if not self._running:
            return
        self._running = False
        self._log_scheduler("scheduler_stopping", wait=wait, timeout=timeout)

        # 清空所有 WAIT 队列（置 CANCELLED）
        for job in list(self._jobs.values()):
            with job.lock:
                self._drain_queue(job, InstanceState.CANCELLED, "调度器停机")

        if wait:
            deadline = time.time() + timeout
            while time.time() < deadline:
                if sum(j.running_count for j in self._jobs.values()) == 0:
                    break
                time.sleep(0.2)
            remaining = sum(j.running_count for j in self._jobs.values())
            if remaining:
                self._log_scheduler("shutdown_timeout", level=logging.WARNING,
                                    running_instances=remaining,
                                    message="停机超时仍有运行实例（线程不可强杀）")

        # 停止事件循环与线程池
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._pool.shutdown(wait=False)
        self._log_scheduler("scheduler_stopped")


# --------------------------------------------------------------------------- #
# 示例
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    sched = Scheduler(timezone="Asia/Shanghai", max_workers=5)

    @sched.task(task_id="demo_sync", cron="*/1 * * * *",
                run_immediately=True, blocking_strategy="WAIT",
                retry_times=1, retry_delay=5, timeout=10)
    def demo_sync():
        logger.info(json.dumps({"biz": "demo_sync running"}, ensure_ascii=False))
        time.sleep(2)

    @sched.task(task_id="demo_seconds", cron="*/10 * * * * *",  # 6 位：每 10 秒
                blocking_strategy="DROP", max_instances=1)
    def demo_seconds():
        logger.info(json.dumps({"biz": "demo_seconds running"}, ensure_ascii=False))
        time.sleep(3)

    try:
        sched.start()  # 阻塞
    except KeyboardInterrupt:
        sched.shutdown(wait=True)
