#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng


def default_if_none(obj: object, default_value: object) -> object:
    return default_value if obj is None or obj == '' else obj
