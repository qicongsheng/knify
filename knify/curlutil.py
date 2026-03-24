#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import shlex
from typing import Dict, Any

import curlify
import requests

from knify import warnutil


class CurlParser:
    """解析 curl 命令并执行 requests 请求"""

    def __init__(self, curl_command: str):
        self.curl_command = curl_command
        self.url = None
        self.method = 'GET'
        self.headers = {}
        self.data = None
        self.params = {}
        self.files = {}
        self.auth = None
        self.cookies = {}
        self.timeout = None
        self.allow_redirects = True
        self.verify = False
        self.proxies = {}
        self.output_file = None
        self.remote_name = False
        self.retry = 0

    def parse(self) -> 'CurlParser':
        """解析 curl 命令"""
        # 移除 curl 命令开头
        cmd = self.curl_command.strip()
        if cmd.startswith('curl '):
            cmd = cmd[5:]

        # 使用 shlex 分割命令，保留引号内容
        try:
            parts = shlex.split(cmd)
        except ValueError:
            # 如果分割失败，尝试简单分割
            parts = cmd.split()

        i = 0
        while i < len(parts):
            part = parts[i]

            # URL (没有 - 开头的参数)
            if not part.startswith('-') and not self.url:
                self.url = part.strip('\'"')
                i += 1
                continue

            # -X, --request: HTTP 方法
            if part in ['-X', '--request']:
                self.method = parts[i + 1].upper()
                i += 2
                continue

            # -H, --header: 请求头
            if part in ['-H', '--header']:
                header = parts[i + 1]
                if ':' in header:
                    key, value = header.split(':', 1)
                    self.headers[key.strip()] = value.strip()
                i += 2
                continue

            # -d, --data, --data-raw, --data-binary: 请求体
            if part in ['-d', '--data', '--data-raw', '--data-binary', '--data-urlencode']:
                self.data = parts[i + 1]
                if self.method == 'GET':
                    self.method = 'POST'
                i += 2
                continue

            # -F, --form: 表单数据
            if part in ['-F', '--form']:
                form_data = parts[i + 1]
                if '=@' in form_data:
                    # 文件上传
                    key, filepath = form_data.split('=@', 1)
                    self.files[key] = open(filepath, 'rb')
                else:
                    # 普通表单字段
                    if '=' in form_data:
                        key, value = form_data.split('=', 1)
                        if not self.data:
                            self.data = {}
                        if isinstance(self.data, dict):
                            self.data[key] = value
                i += 2
                continue

            # --form-string: 表单字符串数据
            if part == '--form-string':
                form_data = parts[i + 1]
                if '=' in form_data:
                    key, value = form_data.split('=', 1)
                    if not self.data:
                        self.data = {}
                    if isinstance(self.data, dict):
                        self.data[key] = value
                i += 2
                continue

            # -u, --user: 认证
            if part in ['-u', '--user']:
                auth_str = parts[i + 1]
                if ':' in auth_str:
                    username, password = auth_str.split(':', 1)
                    self.auth = (username, password)
                i += 2
                continue

            # -b, --cookie: Cookie
            if part in ['-b', '--cookie']:
                cookie_str = parts[i + 1]
                for cookie in cookie_str.split(';'):
                    if '=' in cookie:
                        key, value = cookie.split('=', 1)
                        self.cookies[key.strip()] = value.strip()
                i += 2
                continue

            # -A, --user-agent: User-Agent
            if part in ['-A', '--user-agent']:
                self.headers['User-Agent'] = parts[i + 1]
                i += 2
                continue

            # -e, --referer: Referer
            if part in ['-e', '--referer']:
                self.headers['Referer'] = parts[i + 1]
                i += 2
                continue

            # --compressed: 接受压缩
            if part == '--compressed':
                self.headers['Accept-Encoding'] = 'gzip, deflate, br'
                i += 1
                continue

            # -L, --location: 跟随重定向
            if part in ['-L', '--location']:
                self.allow_redirects = True
                i += 1
                continue

            # -k, --insecure: 不验证 SSL
            if part in ['-k', '--insecure']:
                self.verify = False
                i += 1
                continue

            # -x, --proxy: 代理
            if part in ['-x', '--proxy']:
                proxy = parts[i + 1]
                self.proxies = {'http': proxy, 'https': proxy}
                i += 2
                continue

            # --max-time, --connect-timeout: 超时
            if part in ['--max-time', '--connect-timeout', '-m']:
                self.timeout = float(parts[i + 1])
                i += 2
                continue

            # -G, --get: 强制 GET
            if part in ['-G', '--get']:
                self.method = 'GET'
                i += 1
                continue

            # -o, --output: 输出到文件
            if part in ['-o', '--output']:
                self.output_file = parts[i + 1]
                i += 2
                continue

            # -O, --remote-name: 使用 URL 中的文件名保存
            if part in ['-O', '--remote-name']:
                self.remote_name = True
                i += 1
                continue

            # --retry: 重试次数
            if part == '--retry':
                self.retry = int(parts[i + 1])
                i += 2
                continue

            i += 1

        return self

    def execute(self) -> requests.Response:
        """执行请求并返回响应"""
        if not self.url:
            raise ValueError("未找到 URL")

        # 构建请求参数
        kwargs: Dict[str, Any] = {
            'headers': self.headers,
            'cookies': self.cookies,
            'allow_redirects': self.allow_redirects,
            'verify': self.verify,
        }

        if self.auth:
            kwargs['auth'] = self.auth

        if self.timeout:
            kwargs['timeout'] = self.timeout

        if self.proxies:
            kwargs['proxies'] = self.proxies

        if self.files:
            kwargs['files'] = self.files

        # 处理请求体
        if self.data:
            if isinstance(self.data, str):
                # 尝试解析为 JSON
                if self.data.startswith('{') or self.data.startswith('['):
                    kwargs['data'] = self.data
                    if 'Content-Type' not in self.headers:
                        self.headers['Content-Type'] = 'application/json'
                else:
                    kwargs['data'] = self.data
            else:
                kwargs['data'] = self.data

        # 发送请求，支持重试
        response = None
        for attempt in range(self.retry + 1):
            try:
                response = requests.request(
                    method=self.method,
                    url=self.url,
                    **kwargs
                )
                break
            except Exception as e:
                if attempt == self.retry:
                    raise

        # 保存到文件
        if self.remote_name and not self.output_file:
            filename = self.url.rstrip('/').split('/')[-1].split('?')[0]
            self.output_file = filename or 'output'
        if self.output_file and response:
            with open(self.output_file, 'wb') as f:
                f.write(response.content)

        return response


def request(curl_command: str) -> requests.Response:
    """便捷函数：解析并执行 curl 命令"""
    warnutil.disable_ssl_warnings()
    warnutil.disable_ignore_warnings()
    parser = CurlParser(curl_command)
    parser.parse()
    return parser.execute()


def to_curl(req):
    return curlify.to_curl(req)
