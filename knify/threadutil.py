#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import datetime
import threading

from . import dateutil
from . import listutil
from . import logger

task_lock = threading.Lock()
task_info = {'total': 0, 'processed': 0, 'time_start': None}


def print_task():
    time_used = dateutil.now() - task_info['time_start']
    time_estimate = datetime.timedelta(
        seconds=time_used.total_seconds() * (task_info['total'] / task_info['processed']))
    logger.info("Process: %.2f%% [%s/%s], Estimate: [%s/%s]\r\n" % (
        task_info['processed'] / task_info['total'] * 100, task_info['processed'], task_info['total'],
        dateutil.date_to_str(time_used, dateutil.FORMAT_HMS),
        dateutil.date_to_str(time_estimate, dateutil.FORMAT_HMS)))


def func_wrapper(list_objs_: list, _func_) -> None:
    _func_(list_objs_)
    task_lock.acquire()
    task_info['processed'] = task_info['processed'] + len(list_objs_)
    task_lock.release()


def thread_partition_call(list_obj: list, _func_, thread_num: int, partition_num: int) -> None:
    list_partition = listutil.partition(list_obj, partition_num)
    threads = []
    logger.info("==================== start ====================")
    task_info['total'] = len(list_obj)
    task_info['time_start'] = dateutil.now()
    for index_, list_for_process in enumerate(list_partition):
        t = threading.Thread(target=func_wrapper, args=(list_for_process, _func_))
        t.start()
        threads.append(t)
        if len(threads) == thread_num or index_ == len(list_partition) - 1:
            for t_ in threads:
                t_.join()
            threads = []
            logger.info("====================  end  ====================")
            print_task()
            if index_ < len(list_partition) - 1:
                logger.info("==================== start ====================")
