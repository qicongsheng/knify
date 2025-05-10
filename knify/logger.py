#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import loguru

logger = loguru.logger.opt(depth=1)


def info(msg: str) -> None:
    logger.info(msg)


def warn(msg: str) -> None:
    logger.warning(msg)


def error(msg: str) -> None:
    logger.error(msg)


def debug(msg: str) -> None:
    logger.debug(msg)
