#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng

def partition(list_obj, partition_size):
    return [list_obj[i:i + partition_size] for i in range(0, len(list_obj), partition_size)]
