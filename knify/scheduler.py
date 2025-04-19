#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import threading
import time
from datetime import datetime
from enum import Enum

from . import cron_parser
from . import logger


class BlockingPolicy(Enum):
    """
    阻塞策略枚举
    """
    SKIP = 1  # 跳过当前执行（如果前一次还在运行）
    WAIT = 2  # 等待前一次执行完成（可能会延迟）
    PARALLEL = 3  # 并行执行（默认行为，不阻塞）
    CANCEL_OLD = 4  # 取消前一次执行（如果还在运行）


class TaskScheduler:
    def __init__(self):
        """
        初始化任务调度器
        """
        self.tasks = []
        self._running = False
        self._scheduler_thread = None
        self._task_locks = {}  # 用于跟踪任务执行状态的锁
        self.logger = logger

    def add_task(self, name, cron_expression, func, args=(), kwargs=None,
                 description="", blocking_policy=BlockingPolicy.SKIP):
        """
        添加一个新任务

        :param name: 任务名称
        :param cron_expression: Cron表达式，如 "* * * * *"
        :param func: 要执行的函数
        :param args: 函数的位置参数
        :param kwargs: 函数的关键字参数
        :param description: 任务描述
        :param blocking_policy: 阻塞策略，BlockingPolicy枚举值
        """
        if kwargs is None:
            kwargs = {}

        task = {
            'name': name,
            'cron': cron_expression,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'description': description,
            'blocking_policy': blocking_policy,
            'next_run': self._calculate_next_run(cron_expression),
            'thread': None,  # 存储当前执行线程
            'running': False  # 标记任务是否正在运行
        }

        self.tasks.append(task)
        self._task_locks[name] = threading.Lock()
        self.logger.info(f"Added task '{name}' with schedule '{cron_expression}' and policy {blocking_policy.name}")

    def _calculate_next_run(self, cron_expression, base_time=None):
        """
        计算下一次运行时间

        :param cron_expression: Cron表达式
        :param base_time: 基准时间，默认为当前时间
        :return: 下一次运行的时间戳
        """
        if base_time is None:
            base_time = datetime.now()

        cron = cron_parser.CronParser(cron_expression)
        return cron.get_next_datetime(base_time)

    def _run_task(self, task):
        """
        执行单个任务

        :param task: 要执行的任务字典
        """
        task_name = task['name']
        lock = self._task_locks[task_name]

        try:
            with lock:
                task['running'] = True
                self.logger.info(f"Executing task '{task_name}' with policy {task['blocking_policy'].name}")
                start_time = time.time()

                task['func'](*task['args'], **task['kwargs'])

                duration = time.time() - start_time
                self.logger.info(f"Task '{task_name}' completed in {duration:.2f} seconds")

        except Exception as e:
            self.logger.error(f"Error executing task '{task_name}': {str(e)}")
        finally:
            task['running'] = False

    def _should_execute_task(self, task):
        """
        根据阻塞策略判断是否应该执行任务

        :param task: 任务字典
        :return: 是否应该执行
        """
        policy = task['blocking_policy']

        if not task['running']:
            return True

        if policy == BlockingPolicy.PARALLEL:
            return True
        elif policy == BlockingPolicy.SKIP:
            self.logger.debug(f"Skipping task '{task['name']}' (previous execution still running)")
            return False
        elif policy == BlockingPolicy.WAIT:
            # 等待前一次执行完成
            while task['running']:
                time.sleep(0.1)
            return True
        elif policy == BlockingPolicy.CANCEL_OLD:
            # 取消前一次执行
            if task['thread'] and task['thread'].is_alive():
                # 注意：Python中无法安全地终止线程，这里只是标记
                self.logger.warning(f"Cannot safely cancel running task '{task['name']}'")
                return False
            return True

        return False

    def _scheduler_loop(self):
        """
        调度器主循环
        """
        self.logger.info("Task scheduler started")
        while self._running:
            now = datetime.now()

            for task in self.tasks:
                if task['next_run'] <= now:
                    if self._should_execute_task(task):
                        # 创建并启动线程
                        task_thread = threading.Thread(
                            target=self._run_task,
                            args=(task,),
                            daemon=True
                        )
                        task['thread'] = task_thread
                        task_thread.start()

                    # 计算下一次执行时间
                    task['next_run'] = self._calculate_next_run(
                        task['cron'],
                        task['next_run']
                    )

                    self.logger.debug(
                        f"Scheduled next run for task '{task['name']}' at {task['next_run']}"
                    )

            # 休眠一段时间，避免CPU占用过高
            time.sleep(0.1)

    def start(self):
        """
        启动任务调度器
        """
        if not self._running:
            self._running = True
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True
            )
            self._scheduler_thread.start()
            self.logger.info("Task scheduler started in background thread")

    def stop(self):
        """
        停止任务调度器
        """
        if self._running:
            self._running = False
            if self._scheduler_thread:
                self._scheduler_thread.join(timeout=1)
            self.logger.info("Task scheduler stopped")

    def list_tasks(self):
        """
        列出所有任务及其下次执行时间

        :return: 任务列表
        """
        return [
            {
                'name': task['name'],
                'cron': task['cron'],
                'description': task['description'],
                'blocking_policy': task['blocking_policy'].name,
                'next_run': task['next_run'].strftime('%Y-%m-%d %H:%M:%S'),
                'is_running': task['running']
            }
            for task in self.tasks
        ]

    def __del__(self):
        """
        析构函数，确保调度器停止
        """
        self.stop()


# 示例用法
if __name__ == "__main__":
    def long_running_task(name):
        logger.info(f"[{datetime.now()}] {name} task started")
        time.sleep(10)  # 模拟长时间运行的任务
        logger.info(f"[{datetime.now()}] {name} task completed")


    scheduler = TaskScheduler()

    scheduler.add_task(
        name="skip_task",
        cron_expression="*/5 * * * * *",  # 每5秒
        func=long_running_task,
        args=("Skip",),
        description="跳过执行策略的任务",
        blocking_policy=BlockingPolicy.SKIP
    )

    # 启动调度器
    scheduler.start()

    try:
        # 主线程保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()
