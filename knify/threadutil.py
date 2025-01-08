#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import threading, time
from . import listutil
from . import logger


def thread_partition_call(list_obj: list, func_, thread_num: int, partition_num: int) -> None:
    list_partition = listutil.partition(list_obj, partition_num)
    threads = []
    logger.info("=================== start ===================")
    for index_, list_for_process in enumerate(list_partition):
        t = threading.Thread(target=func_, args=(list_for_process,))
        t.start()
        threads.append(t)
        if len(threads) == thread_num or index_ == len(list_partition) - 1:
            for t_ in threads:
                t_.join()
            threads = []
            logger.info("===================  end  ===================")
            if index_ < len(list_partition) - 1:
                time.sleep(0.5)
                print()
                logger.info("=================== start ===================")
