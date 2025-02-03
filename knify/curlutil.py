#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import re
from typing import Dict, Optional, Union

import requests

from . import warnutil


def curl_to_requests(curl_command: str) -> Optional[Dict[str, Union[str, Dict, bytes]]]:
    # 正则表达式匹配curl命令中的各个部分
    method_pattern = re.compile(r"-X\s+(\w+)")
    url_pattern = re.compile(r"curl\s+'([^']+)'|curl\s+(\S+)")
    header_pattern = re.compile(r"-H\s+'([^']+)'")
    data_pattern = re.compile(r"--data-raw\s+'([^']+)'|--data\s+'([^']+)'")

    # 提取请求方法
    method_match = method_pattern.search(curl_command)
    method = method_match.group(1).upper() if method_match else "GET"

    # 提取URL
    url_match = url_pattern.search(curl_command)
    if not url_match:
        raise ValueError("curl unsupported")
    url = url_match.group(1) if url_match.group(1) else url_match.group(2)

    # 提取请求头
    headers = {}
    for header_match in header_pattern.findall(curl_command):
        key, value = header_match.split(": ", 1)
        headers[key] = value

    # 提取请求体
    data_match = data_pattern.search(curl_command)
    data = data_match.group(1) if data_match else None
    return {"method": method, "url": url, "headers": headers, "data": data.encode('utf-8') if data else None}


def request(curl_command: str) -> Optional[requests.Response]:
    request_params = curl_to_requests(curl_command)
    if not request_params:
        raise ValueError("curl unsupported")
    method = request_params["method"]
    url = request_params["url"]
    headers = request_params["headers"]
    data = request_params["data"]
    warnutil.disable_ssl_warnings()
    return requests.request(method, url, headers=headers, data=data, verify=False)
