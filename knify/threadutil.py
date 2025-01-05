#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import threading
from . import listutil
from . import logger

def thread_partition_call(list_obj: list, func_, thread_num: int, partition_num: int) -> None:
    list_partition = listutil.partition(list_obj, partition_num)
    threads = []
    logger.info("====================start====================")
    for list_for_process in list_partition:
        t = threading.Thread(target=func_, args=(list_for_process,))
        t.start()
        threads.append(t)
        if len(threads) == thread_num:
            for t_ in threads:
                t_.join()
            threads = []
            logger.info("====================start====================")

