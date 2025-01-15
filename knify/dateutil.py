#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import datetime
import time

FORMAT_YYMMDD = "%Y-%m-%d"
FORMAT_HMS = "%H:%M:%S"
FORMAT_YYMMDDHMS = "%Y-%m-%d %H:%M:%S"
FORMAT_YYMMDDHMSF = "%Y-%m-%d %H:%M:%S.%f"


def now() -> datetime:
    return datetime.datetime.now()


def date_to_str(date_obj: datetime, format: str = FORMAT_YYMMDDHMS) -> str:
    if type(date_obj) == datetime.timedelta:
        return (datetime.datetime(1970, 1, 1) + date_obj).strftime(format)
    return date_obj.strftime(format)


def str_to_date(str_obj: str, format: str) -> datetime:
    return datetime.datetime.strptime(str_obj, format)


def date_to_timestamp(date_obj: datetime):
    return time.mktime(date_obj.timetuple())
