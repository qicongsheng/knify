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
    # 解析--location参数, uncurl默认不支持
    follow_redirects = "--location" in curl_command or "-L" in curl_command
    curl_command = curl_command.replace("--location", "").replace("-L", "")
    # 解析 -k 或 --insecure 参数
    verify_ssl = not ("-k" in curl_command or "--insecure" in curl_command)
    curl_command = curl_command.replace("-k", "").replace("--insecure", "")

    context = uncurl.parse_context(curl_command)
    method = context.method.lower() if context.method else 'get'
    return requests.request(
        method.upper(),
        context.url,
        headers=context.headers,
        data=context.data,
        allow_redirects=follow_redirects,
        verify=verify_ssl
    )


def to_curl(req):
    return curlify.to_curl(req)
