#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng


def default_if_none(obj: object, default_value: object) -> object:
    return default_value if obj is None or obj == '' else obj


def has_keys(obj: object) -> bool:
    return obj is not None and len(obj.keys()) > 0


def has_attr(obj: object, key: str) -> bool:
    return hasattr(obj, key)
