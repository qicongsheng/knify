#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import re
from typing import Optional

import curlify
import requests
import uncurl
from requests.auth import HTTPBasicAuth

from . import warnutil


def request(curl_command: str) -> Optional[requests.Response]:
    warnutil.disable_ssl_warnings()
    # 使用正则表达式匹配参数
    insecure_pattern = re.compile(r'\s(--insecure|-k)\s', re.MULTILINE)
    location_pattern = re.compile(r'\s(--location|-L)\s', re.MULTILINE)
    user_agent_pattern = re.compile(r'\s--user-agent\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    cookie_pattern = re.compile(r'\s--cookie\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    form_pattern = re.compile(r'\s--form\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    form_string_pattern = re.compile(r'\s--form-string\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    referer_pattern = re.compile(r'\s--referer\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    user_pattern = re.compile(r'\s--user\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)
    output_pattern = re.compile(r'\s-o\s+["\']?([^"\'\s]+)["\']?', re.MULTILINE)

    # 检查是否包含参数
    verify_ssl = not bool(insecure_pattern.search(curl_command))
    follow_redirects = bool(location_pattern.search(curl_command))
    user_agent = user_agent_pattern.search(curl_command)
    cookie = cookie_pattern.search(curl_command)
    form = form_pattern.search(curl_command)
    form_string = form_string_pattern.search(curl_command)
    referer = referer_pattern.search(curl_command)
    user = user_pattern.search(curl_command)
    output_file = output_pattern.search(curl_command)

    # 移除参数，避免 uncurl 解析失败
    curl_command = insecure_pattern.sub(' ', curl_command)
    curl_command = location_pattern.sub(' ', curl_command)
    curl_command = user_agent_pattern.sub(' ', curl_command)
    curl_command = cookie_pattern.sub(' ', curl_command)
    curl_command = form_pattern.sub(' ', curl_command)
    curl_command = form_string_pattern.sub(' ', curl_command)
    curl_command = referer_pattern.sub(' ', curl_command)
    curl_command = user_pattern.sub(' ', curl_command)
    curl_command = output_pattern.sub(' ', curl_command)

    # 使用 uncurl 解析 curl 命令
    context = uncurl.parse_context(curl_command)
    url = context.url
    headers = context.headers
    data = context.data
    method = context.method.lower() if context.method else 'get'

    # 处理 --user-agent
    if user_agent:
        headers['User-Agent'] = user_agent.group(1)

    # 处理 --cookie
    if cookie:
        headers['Cookie'] = cookie.group(1)

    # 处理 --form 和 --form-string
    files = None
    if form or form_string:
        # 如果存在 --form 或 --form-string，构建 multipart/form-data
        files = {}
        if form:
            # 处理 --form 参数（文件上传）
            form_data = form.group(1)
            if form_data.startswith('@'):
                # 文件上传
                file_path = form_data[1:]
                with open(file_path, 'rb') as f:
                    files['file'] = (file_path, f.read())
            else:
                # 普通表单字段
                key, value = form_data.split('=', 1)
                files[key] = (None, value)
        if form_string:
            # 处理 --form-string 参数（字符串表单字段）
            form_string_data = form_string.group(1)
            key, value = form_string_data.split('=', 1)
            files[key] = (None, value)
        data = None  # 清空 data，因为表单数据通过 files 发送

    # 处理 --referer
    if referer:
        headers['Referer'] = referer.group(1)

    # 处理 --user
    if user:
        username, password = user.group(1).split(':', 1)
        auth = HTTPBasicAuth(username, password)
    else:
        auth = None

    # 使用 requests.request 发送请求
    response = requests.request(
        method,
        url,
        headers=headers,
        data=data,
        files=files,
        auth=auth,
        allow_redirects=follow_redirects,
        verify=verify_ssl
    )

    # 处理 -o 参数，将响应内容保存到文件
    if output_file:
        output_path = output_file.group(1)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"Response content saved to {output_path}")

    return response


def to_curl(req):
    return curlify.to_curl(req)
