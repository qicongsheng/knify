#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from typing import Optional

import curlify
import requests
import uncurl

from . import warnutil


def request(curl_command: str) -> Optional[requests.Response]:
    warnutil.disable_ssl_warnings()
    context = uncurl.parse_context(curl_command)
    method = context.method.lower() if context.method else 'get'
    return requests.request(method, context.url, headers=context.headers, data=context.data)


def to_curl(req):
    return curlify.to_curl(req)
