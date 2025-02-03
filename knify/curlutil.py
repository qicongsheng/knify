#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import json
import re
from typing import Optional

import requests

from . import warnutil


def request(curl_command: str) -> Optional[requests.Response]:
    # 移除换行符和多余的空格
    curl_command = " ".join(curl_command.split())

    # 提取URL（支持--location或直接curl后的URL）
    url_match = re.search(r"(?:--location\s+)?['\"](https?://[^'\"]+)['\"]", curl_command)
    if not url_match:
        raise ValueError("Invalid curl command: URL not found")
    url = url_match.group(1)

    # 提取headers
    headers = {}
    header_matches = re.finditer(r"--header\s+['\"]([^:]+):\s*([^'\"]+)['\"]", curl_command)
    for match in header_matches:
        headers[match.group(1).strip()] = match.group(2).strip()

    # 提取data（JSON数据）
    data_match = re.search(r"--data\s+['\"]({.*?})['\"]", curl_command, re.DOTALL)
    if data_match:
        try:
            data = json.loads(data_match.group(1))  # 解析JSON字符串为Python字典
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON data in curl command")
    else:
        data = None

    # 提取method
    method_match = re.search(r"-X\s+(\w+)", curl_command)
    method = method_match.group(1) if method_match else ("POST" if data else "GET")

    # 处理--location参数（即-L参数）
    follow_redirects = "--location" in curl_command or "-L" in curl_command

    # 处理-k参数（忽略SSL验证）
    verify_ssl = not ("-k" in curl_command or "--insecure" in curl_command)
    warnutil.disable_ssl_warnings()
    # 发送请求
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,  # 使用json参数直接传递字典
        allow_redirects=follow_redirects,
        verify=verify_ssl
    )
    return response
