#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from types import SimpleNamespace


def dic_to_obj(dic: dict, obj: object = None) -> object:
    if obj is not None:
        for key, value in dic.items():
            setattr(obj, key, value)
        return obj
    return SimpleNamespace(**dic)


def obj_to_dic(obj: object = None) -> object:
    return vars(obj) if obj is not None else obj


def default_if_none(obj: object, default_value: object) -> object:
    return default_value if obj is None or obj == '' else obj


def has_keys(obj: object) -> bool:
    return obj is not None and len(obj.keys()) > 0


def has_attr(obj: object, key: str) -> bool:
    return hasattr(obj, key)
