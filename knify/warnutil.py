#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import warnings

import urllib3


def disable_ssl_warnings() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def disable_ignore_warnings() -> None:
    warnings.filterwarnings("ignore")
