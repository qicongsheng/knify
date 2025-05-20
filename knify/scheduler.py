#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
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
    PARALLEL = 2  # 并行执行（默认行为，不阻塞）


class TaskScheduler:

    def __init__(self, timezone=timezone('Asia/Shanghai')):
        """
        初始化任务调度器
        """
        self.logger = logger
        self.scheduler = BlockingScheduler(timezone=timezone)

    def add_task(self, name, cron_expression, func, args=(), kwargs=None,
                 description="", blocking_policy=BlockingPolicy.SKIP, run_immediately=False):
        """
        添加一个新任务
        :param name: 任务名称
        :param cron_expression: Cron表达式，如 "* * * * *"
        :param func: 要执行的函数
        :param args: 函数的位置参数
        :param kwargs: 函数的关键字参数
        :param description: 任务描述
        :param blocking_policy: 阻塞策略，BlockingPolicy枚举值
        :param run_immediately: 是否立即执行
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

        next_run_time = datetime.now(self.scheduler.timezone) if run_immediately else None
        policy_kwargs = self.get_policy_kwargs_by_policy(blocking_policy)
        job = self.scheduler.add_job(func,
                                     CronTrigger.from_crontab(cron_expression, timezone=timezone('Asia/Shanghai')),
                                     name=name, args=args, kwargs=kwargs, next_run_time=next_run_time,
                                     coalesce=policy_kwargs.get('coalesce'),
                                     max_instances=policy_kwargs.get('max_instances'),
                                     misfire_grace_time=policy_kwargs.get('misfire_grace_time'))
        self.logger.info(
            f"Added task '{name}'(id={job.id}) with schedule '{cron_expression}' and policy {blocking_policy.name}")

    def get_policy_kwargs_by_policy(self, blocking_policy):
        # 跳过当前执行（如果前一次还在运行）
        if BlockingPolicy.SKIP == blocking_policy:
            return {"max_instances": 1, "misfire_grace_time": 1, "coalesce": True}
        # 并行执行（默认行为，不阻塞）
        if BlockingPolicy.PARALLEL == blocking_policy:
            return {"max_instances": 99999, "misfire_grace_time": None, "coalesce": False}
        return {}

    def start(self):
        self.logger.info(f"TaskScheduler started")
        self.scheduler.start()


# 示例用法
if __name__ == "__main__":
    def long_running_task(name):
        logger.info(f"[{datetime.now()}] {name} task started")
        time.sleep(120)  # 模拟长时间运行的任务
        logger.info(f"[{datetime.now()}] {name} task completed")


    scheduler = TaskScheduler()
    scheduler.add_task(
        name="skip_task",
        cron_expression="*/1 * * * *",  # 每1分钟
        func=long_running_task,
        args=("Skip",),
        description="跳过执行策略的任务",
        run_immediately=True,
        blocking_policy=BlockingPolicy.SKIP
    )
    # 启动调度器
    scheduler.start()
