"""This module contains the expressions applicable for CronTrigger's fields."""

__all__ = (
    "AllExpression",
    "RangeExpression",
    "WeekdayRangeExpression",
    "WeekdayPositionExpression",
    "LastDayOfMonthExpression",
)

import re
from calendar import monthrange

from knify.apscheduler.util import asint

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


class AllExpression:
    value_re = re.compile(r"\*(?:/(?P<step>\d+))?$")

    def __init__(self, step=None):
        self.step = asint(step)
        if self.step == 0:
            raise ValueError("Increment must be higher than 0")

    def validate_range(self, field_name):
        from knify.apscheduler.triggers.cron.fields import MAX_VALUES, MIN_VALUES

        value_range = MAX_VALUES[field_name] - MIN_VALUES[field_name]
        if self.step and self.step > value_range:
            raise ValueError(
                f"the step value ({self.step}) is higher than the total range of the "
                f"expression ({value_range})"
            )

    def get_next_value(self, date, field):
        start = field.get_value(date)
        minval = field.get_min(date)
        maxval = field.get_max(date)
        start = max(start, minval)

        if not self.step:
            next = start
        else:
            distance_to_next = (self.step - (start - minval)) % self.step
            next = start + distance_to_next

        if next <= maxval:
            return next

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.step == other.step

    def __str__(self):
        if self.step:
            return "*/%d" % self.step
        return "*"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.step})"


class RangeExpression(AllExpression):
    value_re = re.compile(r"(?P<first>\d+)(?:-(?P<last>\d+))?(?:/(?P<step>\d+))?$")

    def __init__(self, first, last=None, step=None):
        super().__init__(step)
        first = asint(first)
        last = asint(last)
        if last is None and step is None:
            last = first
        if last is not None and first > last:
            raise ValueError(
                "The minimum value in a range must not be higher than the maximum"
            )
        self.first = first
        self.last = last

    def validate_range(self, field_name):
        from knify.apscheduler.triggers.cron.fields import MAX_VALUES, MIN_VALUES

        super().validate_range(field_name)
        if self.first < MIN_VALUES[field_name]:
            raise ValueError(
                f"the first value ({self.first}) is lower than the minimum value ({MIN_VALUES[field_name]})"
            )
        if self.last is not None and self.last > MAX_VALUES[field_name]:
            raise ValueError(
                f"the last value ({self.last}) is higher than the maximum value ({MAX_VALUES[field_name]})"
            )
        value_range = (self.last or MAX_VALUES[field_name]) - self.first
        if self.step and self.step > value_range:
            raise ValueError(
                f"the step value ({self.step}) is higher than the total range of the "
                f"expression ({value_range})"
            )

    def get_next_value(self, date, field):
        startval = field.get_value(date)
        minval = field.get_min(date)
        maxval = field.get_max(date)

        # Apply range limits
        minval = max(minval, self.first)
        maxval = min(maxval, self.last) if self.last is not None else maxval
        nextval = max(minval, startval)

        # Apply the step if defined
        if self.step:
            distance_to_next = (self.step - (nextval - minval)) % self.step
            nextval += distance_to_next

        return nextval if nextval <= maxval else None

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.first == other.first
            and self.last == other.last
        )

    def __str__(self):
        if self.last != self.first and self.last is not None:
            range = "%d-%d" % (self.first, self.last)
        else:
            range = str(self.first)

        if self.step:
            return "%s/%d" % (range, self.step)

        return range

    def __repr__(self):
        args = [str(self.first)]
        if self.last != self.first and self.last is not None or self.step:
            args.append(str(self.last))

        if self.step:
            args.append(str(self.step))

        return "{}({})".format(self.__class__.__name__, ", ".join(args))


class MonthRangeExpression(RangeExpression):
    value_re = re.compile(r"(?P<first>[a-z]+)(?:-(?P<last>[a-z]+))?", re.IGNORECASE)

    def __init__(self, first, last=None):
        try:
            first_num = MONTHS.index(first.lower()) + 1
        except ValueError:
            raise ValueError(f'Invalid month name "{first}"')

        if last:
            try:
                last_num = MONTHS.index(last.lower()) + 1
            except ValueError:
                raise ValueError(f'Invalid month name "{last}"')
        else:
            last_num = None

        super().__init__(first_num, last_num)

    def __str__(self):
        if self.last != self.first and self.last is not None:
            return f"{MONTHS[self.first - 1]}-{MONTHS[self.last - 1]}"
        return MONTHS[self.first - 1]

    def __repr__(self):
        args = [f"'{MONTHS[self.first]}'"]
        if self.last != self.first and self.last is not None:
            args.append(f"'{MONTHS[self.last - 1]}'")
        return "{}({})".format(self.__class__.__name__, ", ".join(args))


class WeekdayRangeExpression(RangeExpression):
    value_re = re.compile(r"(?P<first>[a-z]+)(?:-(?P<last>[a-z]+))?", re.IGNORECASE)

    def __init__(self, first, last=None):
        try:
            first_num = WEEKDAYS.index(first.lower())
        except ValueError:
            raise ValueError(f'Invalid weekday name "{first}"')

        if last:
            try:
                last_num = WEEKDAYS.index(last.lower())
            except ValueError:
                raise ValueError(f'Invalid weekday name "{last}"')
        else:
            last_num = None

        super().__init__(first_num, last_num)

    def __str__(self):
        if self.last != self.first and self.last is not None:
            return f"{WEEKDAYS[self.first]}-{WEEKDAYS[self.last]}"
        return WEEKDAYS[self.first]

    def __repr__(self):
        args = [f"'{WEEKDAYS[self.first]}'"]
        if self.last != self.first and self.last is not None:
            args.append(f"'{WEEKDAYS[self.last]}'")
        return "{}({})".format(self.__class__.__name__, ", ".join(args))


class WeekdayPositionExpression(AllExpression):
    options = ["1st", "2nd", "3rd", "4th", "5th", "last"]
    value_re = re.compile(
        r"(?P<option_name>{}) +(?P<weekday_name>(?:\d+|\w+))".format("|".join(options)),
        re.IGNORECASE,
    )

    def __init__(self, option_name, weekday_name):
        super().__init__(None)
        try:
            self.option_num = self.options.index(option_name.lower())
        except ValueError:
            raise ValueError(f'Invalid weekday position "{option_name}"')

        try:
            self.weekday = WEEKDAYS.index(weekday_name.lower())
        except ValueError:
            raise ValueError(f'Invalid weekday name "{weekday_name}"')

    def get_next_value(self, date, field):
        # Figure out the weekday of the month's first day and the number of days in that month
        first_day_wday, last_day = monthrange(date.year, date.month)

        # Calculate which day of the month is the first of the target weekdays
        first_hit_day = self.weekday - first_day_wday + 1
        if first_hit_day <= 0:
            first_hit_day += 7

        # Calculate what day of the month the target weekday would be
        if self.option_num < 5:
            target_day = first_hit_day + self.option_num * 7
        else:
            target_day = first_hit_day + ((last_day - first_hit_day) // 7) * 7

        if target_day <= last_day and target_day >= date.day:
            return target_day

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.option_num == other.option_num
            and self.weekday == other.weekday
        )

    def __str__(self):
        return f"{self.options[self.option_num]} {WEEKDAYS[self.weekday]}"

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.options[self.option_num]}', '{WEEKDAYS[self.weekday]}')"


class LastDayOfMonthExpression(AllExpression):
    value_re = re.compile(r"last", re.IGNORECASE)

    def __init__(self):
        super().__init__(None)

    def get_next_value(self, date, field):
        return monthrange(date.year, date.month)[1]

    def __str__(self):
        return "last"

    def __repr__(self):
        return f"{self.__class__.__name__}()"
