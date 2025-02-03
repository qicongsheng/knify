#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import re
from typing import Optional

import requests

from . import warnutil


def request(curl_command: str) -> Optional[requests.Response]:
    # 提取URL
    url_match = re.search(r"curl\s+['\"]?([^'\"]+)['\"]?", curl_command)
    if not url_match:
        raise ValueError("Invalid curl command: URL not found")
    url = url_match.group(1)

    # 提取headers
    headers = {}
    header_matches = re.finditer(r"-H\s+['\"]?([^:]+):\s*([^'\"]+)['\"]?", curl_command)
    for match in header_matches:
        headers[match.group(1).strip()] = match.group(2).strip()

    # 提取data
    data_match = re.search(r"--data-raw\s+['\"]?([^'\"]+)['\"]?", curl_command)
    data = data_match.group(1) if data_match else None

    # 提取method
    method_match = re.search(r"-X\s+(\w+)", curl_command)
    method = method_match.group(1) if method_match else ("POST" if data else "GET")

    # 处理--location参数（即-L参数）
    follow_redirects = "-L" in curl_command or "--location" in curl_command

    # 处理-k参数（忽略SSL验证）
    verify_ssl = not ("-k" in curl_command or "--insecure" in curl_command)

    # 发送请求
    warnutil.disable_ssl_warnings()
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        data=data,
        allow_redirects=follow_redirects,
        verify=verify_ssl
    )
    return response
