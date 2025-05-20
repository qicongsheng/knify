#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import datetime
import threading
import traceback

from knify import dateutil
from knify import listutil
from knify import logger


def async_call(async_func, callback_func, *args, **kwargs):
    def wrapper():
        result = None
        error = None
        try:
            result = async_func(*args, **kwargs)
        except:
            error = traceback.format_exc()
        callback_func(result, **{'error': error})

    thread = threading.Thread(target=wrapper)
    thread.start()


class PartitionExecutor:
    def __init__(self):
        self.task_lock = threading.Lock()
        self.task_info = {'total': 0, 'processed': 0, 'time_start': None}

    def print_task(self):
        time_used = dateutil.now() - self.task_info['time_start']
        time_estimate = datetime.timedelta(
            seconds=time_used.total_seconds() * (self.task_info['total'] / self.task_info['processed']))
        logger.info("Process: %.2f%% [%s/%s], Estimate: [%s/%s]\r\n" % (
            self.task_info['processed'] / self.task_info['total'] * 100, self.task_info['processed'],
            self.task_info['total'],
            dateutil.date_to_str(time_used, dateutil.FORMAT_HMS),
            dateutil.date_to_str(time_estimate, dateutil.FORMAT_HMS)))

    def func_wrapper(self, list_objs_: list, _func_) -> None:
        _func_(list_objs_)
        self.task_lock.acquire()
        self.task_info['processed'] = self.task_info['processed'] + len(list_objs_)
        self.task_lock.release()

    def thread_partition_call(self, list_obj: list, _func_, thread_num: int, partition_num: int) -> None:
        list_partition = listutil.partition(list_obj, partition_num)
        threads = []
        logger.info("==================== start ====================")
        self.task_info['total'] = len(list_obj)
        self.task_info['time_start'] = dateutil.now()
        for index_, list_for_process in enumerate(list_partition):
            t = threading.Thread(target=func_wrapper, args=(list_for_process, _func_))
            t.start()
            threads.append(t)
            if len(threads) == thread_num or index_ == len(list_partition) - 1:
                for t_ in threads:
                    t_.join()
                threads = []
                logger.info("====================  end  ====================")
                self.print_task()
                if index_ < len(list_partition) - 1:
                    logger.info("==================== start ====================")


partition_executor = PartitionExecutor()
