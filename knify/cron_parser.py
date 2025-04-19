#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Union, Dict, Any, Optional


class CronFieldType(Enum):
    SECOND = 0
    MINUTE = 1
    HOUR = 2
    DAY = 3
    MONTH = 4
    WEEKDAY = 5
    YEAR = 6


class CronParser:
    """
    支持秒级精度和问号的cron表达式解析器
    格式: [秒] [分] [时] [日] [月] [周] [年] (可选)
    标准格式: * * * * * * *
    特殊字符: ? 表示不指定值(仅用于日或周字段)
    """

    FIELD_NAMES = ['second', 'minute', 'hour', 'day', 'month', 'weekday', 'year']
    FIELD_RANGES = [
        (0, 59),  # second
        (0, 59),  # minute
        (0, 23),  # hour
        (1, 31),  # day
        (1, 12),  # month
        (0, 6),  # weekday (0=Sunday)
        (1970, 2099)  # year
    ]
    MONTH_ALIAS = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    WEEKDAY_ALIAS = {
        'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6
    }

    def __init__(self, cron_str: str):
        self.cron_str = cron_str.strip()
        self.fields = self._parse_cron_string()

    def _parse_cron_string(self) -> Dict[str, Any]:
        """解析cron字符串为字段字典"""
        parts = self.cron_str.split()

        if len(parts) < 5 or len(parts) > 7:
            raise ValueError(f"Invalid cron expression. Expected 5-7 fields, got {len(parts)}")

        # 处理标准5字段和扩展6-7字段的情况
        fields = {}
        if len(parts) == 5:
            # 标准5字段: 分 时 日 月 周
            fields['second'] = self._parse_field('0', CronFieldType.SECOND)
            for i, field_type in enumerate([CronFieldType.MINUTE, CronFieldType.HOUR,
                                            CronFieldType.DAY, CronFieldType.MONTH,
                                            CronFieldType.WEEKDAY], 1):
                fields[self.FIELD_NAMES[i]] = self._parse_field(parts[i - 1], field_type)
            fields['year'] = self._parse_field('*', CronFieldType.YEAR)
        else:
            # 6或7字段: 秒 分 时 日 月 周 [年]
            for i, field_type in enumerate([
                CronFieldType.SECOND, CronFieldType.MINUTE, CronFieldType.HOUR,
                CronFieldType.DAY, CronFieldType.MONTH, CronFieldType.WEEKDAY,
                CronFieldType.YEAR
            ]):
                if i < len(parts):
                    fields[self.FIELD_NAMES[i]] = self._parse_field(parts[i], field_type)
                else:
                    # 默认年字段为*
                    fields[self.FIELD_NAMES[i]] = self._parse_field('*', field_type)

        # 检查日和周的冲突
        if (fields['day'] != [x for x in range(1, 32)] and
                fields['weekday'] != [x for x in range(0, 7)]):
            raise ValueError("Cannot specify both day and weekday constraints (use ? for one of them)")

        return fields

    def _parse_field(self, field_str: str, field_type: CronFieldType) -> List[int]:
        """解析单个cron字段"""
        field_str = field_str.upper()
        min_val, max_val = self.FIELD_RANGES[field_type.value]

        # 处理问号(仅对日和周字段有效)
        if field_str == '?':
            if field_type not in (CronFieldType.DAY, CronFieldType.WEEKDAY):
                raise ValueError(
                    f"Question mark (?) can only be used for day or weekday fields, not for {self.FIELD_NAMES[field_type.value]}")
            return [x for x in range(min_val, max_val + 1)]

        # 处理别名
        if field_type == CronFieldType.MONTH:
            for alias, value in self.MONTH_ALIAS.items():
                field_str = field_str.replace(alias, str(value))
        elif field_type == CronFieldType.WEEKDAY:
            for alias, value in self.WEEKDAY_ALIAS.items():
                field_str = field_str.replace(alias, str(value))

        # 分割多个表达式
        parts = []
        for part in field_str.split(','):
            part = part.strip()
            if not part or part == '?':  # 单独的问号已经处理过
                continue

            # 处理步长
            step_parts = part.split('/')
            base_part = step_parts[0]
            step = 1
            if len(step_parts) > 1:
                try:
                    step = int(step_parts[1])
                except ValueError:
                    raise ValueError(f"Invalid step value in '{field_str}'")
                if step < 1:
                    raise ValueError(f"Step value must be positive in '{field_str}'")

            # 处理范围或通配符
            if base_part == '*':
                start, end = min_val, max_val
            elif '-' in base_part:
                start_end = base_part.split('-')
                if len(start_end) != 2:
                    raise ValueError(f"Invalid range in '{field_str}'")
                try:
                    start = self._parse_single_value(start_end[0], field_type)
                    end = self._parse_single_value(start_end[1], field_type)
                except ValueError as e:
                    raise ValueError(f"Invalid range in '{field_str}': {str(e)}")

                if start > end:
                    raise ValueError(f"Start must be <= end in range '{field_str}'")
            else:
                try:
                    start = end = self._parse_single_value(base_part, field_type)
                except ValueError as e:
                    raise ValueError(f"Invalid value in '{field_str}': {str(e)}")

            # 验证范围
            if start < min_val or end > max_val:
                raise ValueError(
                    f"Value out of range ({min_val}-{max_val}) in '{field_str}'")

            # 生成序列
            parts.extend(range(start, end + 1, step))

        # 去重排序
        result = sorted(list(set(parts)))

        # 特殊处理周字段的0和7都表示周日
        if field_type == CronFieldType.WEEKDAY:
            if 7 in result:
                result.remove(7)
                if 0 not in result:
                    result.append(0)
                    result.sort()

        return result

    def _parse_single_value(self, value_str: str, field_type: CronFieldType) -> int:
        """解析单个值"""
        try:
            return int(value_str)
        except ValueError:
            raise ValueError(f"Invalid integer value '{value_str}'")

    def get_next(self, basetime: Optional[Union[float, int, datetime]] = None) -> float:
        """
        获取下一个执行时间的时间戳
        :param basetime: 基准时间，可以是时间戳或datetime对象，为空则取当前时间
        :return: 下一个执行时间的时间戳
        :raises: ValueError 如果无法找到下一个执行时间
        """
        if basetime is None:
            basetime = time.time()
        elif isinstance(basetime, datetime):
            basetime = basetime.timestamp()

        dt = datetime.fromtimestamp(basetime)
        dt += timedelta(seconds=1)  # 从下一秒开始

        for _ in range(100000):  # 防止无限循环
            # 检查年
            if dt.year not in self.fields['year']:
                next_years = [y for y in self.fields['year'] if y > dt.year]
                if not next_years:
                    raise ValueError(f"No valid year found after {dt.year}")
                next_year = min(next_years)
                dt = datetime(next_year, 1, 1, dt.hour, dt.minute, dt.second)
                continue

            # 检查月
            if dt.month not in self.fields['month']:
                next_months = [m for m in self.fields['month'] if m > dt.month]
                if not next_months:
                    next_year = min(y for y in self.fields['year'] if y > dt.year)
                    next_month = min(self.fields['month'])
                    dt = datetime(next_year, next_month, 1, dt.hour, dt.minute, dt.second)
                else:
                    next_month = min(next_months)
                    dt = datetime(dt.year, next_month, 1, dt.hour, dt.minute, dt.second)
                continue

            # 检查日和周
            day_valid = dt.day in self.fields['day']
            weekday_valid = dt.weekday() in self.fields['weekday']
            current_time_sec = dt.hour * 3600 + dt.minute * 60 + dt.second
            target_time_sec = (self.fields['hour'][0] * 3600 +
                               self.fields['minute'][0] * 60 +
                               self.fields['second'][0])

            # 情况1: 日无限制(使用?)，周有限制
            if (self.fields['day'] == list(range(1, 32)) and
                    self.fields['weekday'] != list(range(0, 7))):

                if (not weekday_valid or
                        (weekday_valid and current_time_sec >= target_time_sec)):

                    # 找到下一个最近的周几
                    next_weekday = min([d for d in self.fields['weekday'] if d > dt.weekday()],
                                       default=self.fields['weekday'][0])
                    days_to_add = (next_weekday - dt.weekday()) % 7
                    if days_to_add == 0:  # 同一天但时间已过
                        days_to_add = 7
                    dt += timedelta(days=days_to_add)
                    dt = dt.replace(hour=self.fields['hour'][0],
                                    minute=self.fields['minute'][0],
                                    second=self.fields['second'][0])
                    continue

            # 情况2: 日有限制，周无限制(使用?)
            elif (self.fields['day'] != list(range(1, 32)) and (self.fields['weekday'] == list(range(0, 7)))):
                if not day_valid:
                    next_days = [d for d in self.fields['day'] if d > dt.day]
                    if next_days:
                        next_day = min(next_days)
                        try:
                            dt = dt.replace(day=next_day)
                        except ValueError:  # 无效日期（如2月30日）
                            dt = self._add_months(dt, 1).replace(day=min(self.fields['day']))
                    else:
                        dt = self._add_months(dt, 1).replace(day=min(self.fields['day']))
                    continue

            # 情况3: 日和周都有限制
            elif not (self.fields['day'] == list(range(1, 32)) or
                      self.fields['weekday'] == list(range(0, 7))):

                if not day_valid or not weekday_valid:
                    dt += timedelta(days=1)
                    continue

            # 检查时
            if dt.hour not in self.fields['hour']:
                next_hours = [h for h in self.fields['hour'] if h > dt.hour]
                if not next_hours:
                    dt += timedelta(days=1)
                    next_hour = min(self.fields['hour'])
                    dt = dt.replace(hour=next_hour, minute=0, second=0)
                else:
                    next_hour = min(next_hours)
                    dt = dt.replace(hour=next_hour, minute=0, second=0)
                continue

            # 检查分
            if dt.minute not in self.fields['minute']:
                next_minutes = [m for m in self.fields['minute'] if m > dt.minute]
                if not next_minutes:
                    dt += timedelta(hours=1)
                    next_minute = min(self.fields['minute'])
                    dt = dt.replace(minute=next_minute, second=0)
                else:
                    next_minute = min(next_minutes)
                    dt = dt.replace(minute=next_minute, second=0)
                continue

            # 检查秒
            if dt.second not in self.fields['second']:
                next_seconds = [s for s in self.fields['second'] if s > dt.second]
                if not next_seconds:
                    dt += timedelta(minutes=1)
                    next_second = min(self.fields['second'])
                    dt = dt.replace(second=next_second)
                else:
                    next_second = min(next_seconds)
                    dt = dt.replace(second=next_second)
                continue

            # 所有条件满足
            return dt.timestamp()

        raise ValueError("Unable to find next execution time after 100000 iterations")


    def _add_months(self, dt: datetime, months: int) -> datetime:
        """添加指定月数到datetime"""
        year = dt.year + (dt.month + months - 1) // 12
        month = (dt.month + months - 1) % 12 + 1
        max_day = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
                   31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
        day = min(dt.day, max_day)
        return dt.replace(year=year, month=month, day=day)

    def _days_in_month(self, year: int, month: int) -> int:
        """返回指定年月有多少天"""
        return [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

    def get_next_datetime(self, basetime: Optional[Union[float, int, datetime]] = datetime.now()) -> datetime:
        """
        获取下一个执行时间的datetime对象
        :param basetime: 基准时间，可以是时间戳或datetime对象，为空则取当前时间
        :return: 下一个执行时间的datetime对象
        """
        timestamp = self.get_next(basetime)
        return datetime.fromtimestamp(timestamp)

    def get_schedule(self, from_time: Optional[Union[float, int, datetime]] = None,
                     to_time: Optional[Union[float, int, datetime]] = None,
                     count: int = 10) -> List[datetime]:
        """
        获取多个执行时间
        :param from_time: 起始时间，可以是时间戳或datetime对象，为空则取当前时间
        :param to_time: 结束时间，可以是时间戳或datetime对象
        :param count: 最多返回的执行时间数量
        :return: 执行时间列表(datetime对象)
        """
        if from_time is None:
            from_time = time.time()
        elif isinstance(from_time, datetime):
            from_time = from_time.timestamp()

        if to_time is not None:
            if isinstance(to_time, datetime):
                to_time = to_time.timestamp()
            if to_time <= from_time:
                raise ValueError("to_time must be after from_time")

        result = []
        current_time = from_time

        for _ in range(count):
            next_time = self.get_next(current_time)
            if to_time is not None and next_time > to_time:
                break
            result.append(datetime.fromtimestamp(next_time))
            current_time = next_time

        return result

    def explain(self) -> str:
        """解释cron表达式的含义"""
        explanations = []

        for field in self.FIELD_NAMES:
            values = self.fields[field]
            if not values:
                explanations.append(f"{field}: no valid values")
                continue

            if field in ('day', 'weekday') and '?' in self.cron_str:
                if field == 'day' and self.fields['day'] == [x for x in range(1, 32)]:
                    explanations.append(f"{field}: not specified (?)")
                    continue
                if field == 'weekday' and self.fields['weekday'] == [x for x in range(0, 7)]:
                    explanations.append(f"{field}: not specified (?)")
                    continue

            if len(values) == 1:
                explanations.append(f"{field}: at {values[0]}")
            elif len(values) == (self.FIELD_RANGES[self.FIELD_NAMES.index(field)][1] -
                                 self.FIELD_RANGES[self.FIELD_NAMES.index(field)][0] + 1):
                explanations.append(f"{field}: every {field}")
            else:
                step = self._detect_step(values)
                if step:
                    explanations.append(f"{field}: every {step} {field}s from {values[0]} to {values[-1]}")
                else:
                    explanations.append(f"{field}: at {', '.join(map(str, values))}")

        return "\n".join(explanations)

    def _detect_step(self, values: List[int]) -> Union[int, None]:
        """检测步长模式"""
        if len(values) < 2:
            return None

        step = values[1] - values[0]
        for i in range(1, len(values)):
            if values[i] - values[i - 1] != step:
                return None

        return step

    def __str__(self) -> str:
        return f"CronParser('{self.cron_str}')"


# 使用示例
if __name__ == "__main__":
    cron2 = CronParser("*/5 * * * *")  # 每月1日午夜，不指定周几
    print(f"Next execution: {cron2.get_next_datetime()}")

    cron2 = CronParser("5 23 * * *")  # 每月1日午夜，不指定周几
    print(f"Next execution: {cron2.get_next_datetime()}")

    # 使用问号的cron表达式
    cron1 = CronParser("0 0 12 ? * MON")  # 每周一中午12点，不指定具体日
    print(f"Next execution: {cron1.get_next_datetime()}")

    cron2 = CronParser("0 0 0 1 * ?")  # 每月1日午夜，不指定周几
    print(f"Next execution: {cron2.get_next_datetime()}")

