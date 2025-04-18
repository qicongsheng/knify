#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import threading
import time
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Optional, Dict

from croniter import croniter

from . import logger


class BlockingPolicy(Enum):
    """任务阻塞策略枚举"""
    SKIP = auto()  # 跳过正在执行的任务实例‌:ml-citation{ref="1,8" data="citationList"}
    WAIT = auto()  # 等待当前实例完成‌:ml-citation{ref="5,7" data="citationList"}
    FORCE = auto()  # 强制新建线程执行‌:ml-citation{ref="6,8" data="citationList"}


class CronScheduler:
    def __init__(self):
        """初始化调度器"""
        self._tasks = []
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._active_tasks: Dict[str, Dict] = {}  # 记录任务执行状态‌:ml-citation{ref="6,7" data="citationList"}

    def add_task(
            self,
            func: Callable,
            cron_expr: str,
            args: tuple = (),
            kwargs: Optional[dict] = None,
            name: Optional[str] = None,
            policy: BlockingPolicy = BlockingPolicy.SKIP,  # 单任务阻塞策略‌:ml-citation{ref="1,6" data="citationList"}
            max_instances: int = 1  # 最大并发实例数‌:ml-citation{ref="6,7" data="citationList"}
    ) -> str:
        """
        添加定时任务
        参数:
            policy: 阻塞策略(默认SKIP)‌:ml-citation{ref="1,6" data="citationList"}
            max_instances: 允许同时运行的最大实例数‌:ml-citation{ref="6,7" data="citationList"}
        """
        task_id = f"task_{len(self._tasks) + 1}"
        next_run = self._calculate_next_run(cron_expr)

        task = {
            'id': task_id,
            'func': func,
            'cron': cron_expr,
            'args': args,
            'kwargs': kwargs or {},
            'name': name or task_id,
            'policy': policy,
            'max_instances': max_instances,
            'next_run': next_run,
            'lock': threading.RLock()  # 任务级锁‌:ml-citation{ref="5,7" data="citationList"}
        }

        with self._lock:
            self._tasks.append(task)
        return task_id

    def _calculate_next_run(self, cron_expr: str) -> float:
        """计算下次运行时间"""
        return croniter(cron_expr, datetime.now()).get_next(float)

    def _execute_task(self, task: Dict) -> None:
        """执行任务包装方法"""
        try:
            task['func'](*task['args'], **task['kwargs'])
        except Exception as e:
            logger.info(f"[{datetime.now()}] 任务执行失败 {task['name']}: {e}")
        finally:
            with self._lock:
                self._active_tasks[task['id']]['count'] -= 1
                if self._active_tasks[task['id']]['count'] == 0:
                    self._active_tasks.pop(task['id'])

    def _should_execute(self, task: Dict) -> bool:
        """判断是否满足执行条件‌:ml-citation{ref="1,5" data="citationList"}"""
        with self._lock:
            active_info = self._active_tasks.get(task['id'], {'count': 0})

            if active_info['count'] >= task['max_instances']:
                return False

            if task['policy'] == BlockingPolicy.SKIP and active_info['count'] > 0:
                return False

            return True

    def _run_loop(self) -> None:
        """调度主循环‌:ml-citation{ref="1,5" data="citationList"}"""
        while self._running:
            now = time.time()
            tasks_to_run = []

            with self._lock:
                for task in self._tasks:
                    if now >= task['next_run'] and self._should_execute(task):
                        tasks_to_run.append(task)
                        task['next_run'] = self._calculate_next_run(task['cron'])

                        # 更新活动任务计数
                        if task['id'] not in self._active_tasks:
                            self._active_tasks[task['id']] = {'count': 0}
                        self._active_tasks[task['id']]['count'] += 1

            # 启动任务线程
            for task in tasks_to_run:
                if task['policy'] == BlockingPolicy.WAIT:
                    with task['lock']:  # 串行执行‌:ml-citation{ref="5,7" data="citationList"}
                        self._execute_task(task)
                else:
                    # SKIP/FORCE策略使用新线程‌:ml-citation{ref="6,8" data="citationList"}
                    threading.Thread(
                        target=self._execute_task,
                        args=(task,),
                        daemon=True
                    ).start()

            # 计算下次检查间隔
            next_check = min(
                (t['next_run'] for t in self._tasks),
                default=now + 1
            )
            time.sleep(max(0, min(next_check - now, 1)))

    def start(self) -> None:
        """启动调度器‌:ml-citation{ref="1,8" data="citationList"}"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """停止调度器‌:ml-citation{ref="5,7" data="citationList"}"""
        self._running = False
        if wait and self._thread:
            self._thread.join()
