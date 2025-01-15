#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from collections import defaultdict
from typing import Callable


def partition(list_obj: list, partition_size: int) -> list[object]:
    return [list_obj[i:i + partition_size] for i in range(0, len(list_obj), partition_size)]


def groupby(list_obj: list, key_func: Callable[[object], object],
            value_func: Callable[[object], object] = lambda v_: v_) -> dict[object, object]:
    grouped = defaultdict(list)
    for obj in list_obj:
        grouped[key_func(obj)].append(value_func(obj))
    return grouped


def is_empty(list_obj: list):
    return list_obj is None or len(list_obj) == 0


def is_not_empty(list_obj: list):
    return list_obj is not None and len(list_obj) > 0


def find_first(list_obj: list) -> object:
    return list_obj[0] if list_obj is not None and len(list_obj) > 0 else None
