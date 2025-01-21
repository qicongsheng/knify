#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import datetime
import time

import pytz

FORMAT_YYMMDD = "%Y-%m-%d"
FORMAT_HMS = "%H:%M:%S"
FORMAT_YYMMDDHMS = "%Y-%m-%d %H:%M:%S"
FORMAT_YYMMDDHMSF = "%Y-%m-%d %H:%M:%S.%f"
FORMAT_YYMMDDHMS_STRICT = "%Y%m%d%H%M%S"

TIMEZONE_UTC = 'UTC'
TIMEZONE_SHANGHAI = 'Asia/Shanghai'


def now() -> datetime:
    return datetime.datetime.now()


def now_str(format: str = FORMAT_YYMMDDHMS) -> str:
    return date_to_str(now(), format)


def reformat(str_obj: str, format_old: str, format_new: str = FORMAT_YYMMDDHMS) -> str:
    return date_to_str(str_to_date(str_obj, format_old), format_new)


def date_to_str(date_obj: datetime, format: str = FORMAT_YYMMDDHMS):
    if date_obj is None:
        return None
    if type(date_obj) == datetime.timedelta:
        return (datetime.datetime(1970, 1, 1) + date_obj).strftime(format)
    return date_obj.strftime(format)


def date_as_timezone(date_obj: datetime, timezone: str = TIMEZONE_UTC):
    zone = pytz.timezone(timezone)
    return date_obj.astimezone(zone) if date_obj is not None else date_obj


def str_as_timezone(str_obj: datetime, format: str = FORMAT_YYMMDDHMS, timezone: str = TIMEZONE_UTC):
    return date_to_str(date_as_timezone(str_to_date(str_obj, format), timezone), format)


def str_to_date(str_obj: str, format: str) -> datetime:
    if str_obj is None:
        return None
    return datetime.datetime.strptime(str_obj, format)


def date_to_timestamp(date_obj: datetime):
    if date_obj is None:
        return None
    return time.mktime(date_obj.timetuple())


def add_hours(date_obj: datetime, hours: int = 0):
    return date_obj + datetime.timedelta(hours=hours) if date_obj is not None else date_obj


def add_days(date_obj: datetime, days: int = 0):
    return date_obj + datetime.timedelta(days=days) if date_obj is not None else date_obj


def add_minutes(date_obj: datetime, minutes: int = 0):
    return date_obj + datetime.timedelta(minutes=minutes) if date_obj is not None else date_obj
