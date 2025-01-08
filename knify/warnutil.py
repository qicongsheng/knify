#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import urllib3


def disable_ssl_warnings() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
