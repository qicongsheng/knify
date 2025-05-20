#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import threading
import time
from datetime import datetime
from enum import Enum

from pytz import timezone

from knify import logger
from knify.apscheduler.schedulers.blocking import BlockingScheduler
from knify.apscheduler.triggers.cron import CronTrigger


class BlockingPolicy(Enum):
    """
    阻塞策略枚举
    """
    SKIP = 1  # 跳过当前执行（如果前一次还在运行）
    WAIT = 2  # 等待前一次执行完成（可能会延迟）
    PARALLEL = 3  # 并行执行（默认行为，不阻塞）
    CANCEL_OLD = 4  # 取消前一次执行（如果还在运行）


class TaskScheduler:
    def __init__(self, timezone=timezone('Asia/Shanghai')):
        """
        初始化任务调度器
        """
        self.tasks = []
        self._running = False
        self._scheduler_thread = None
        self._task_locks = {}  # 用于跟踪任务执行状态的锁
        self.logger = logger
        self.scheduler = BlockingScheduler(timezone=timezone)

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
            'blocking_policy': blocking_policy
        }

        self.tasks.append(task)
        self._task_locks[name] = threading.Lock()
        self.logger.info(f"Added task '{name}' with schedule '{cron_expression}' and policy {blocking_policy.name}")
        self.scheduler.add_job(func, CronTrigger.from_crontab(cron_expression, timezone=timezone('Asia/Shanghai')),
                               name=name, args=args, kwargs=kwargs)

    def start(self):
        self.logger.info(f"TaskScheduler started")
        self.scheduler.start()


# 示例用法
if __name__ == "__main__":
    def long_running_task(name):
        logger.info(f"[{datetime.now()}] {name} task started")
        time.sleep(10)  # 模拟长时间运行的任务
        logger.info(f"[{datetime.now()}] {name} task completed")


    scheduler = TaskScheduler()
    scheduler.add_task(
        name="skip_task",
        cron_expression="*/1 * * * *",  # 每5秒
        func=long_running_task,
        args=("Skip",),
        description="跳过执行策略的任务",
        blocking_policy=BlockingPolicy.SKIP
    )
    # 启动调度器
    scheduler.start()
