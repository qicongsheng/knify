#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng

import json
from typing import Any


def load_from_file(file_path: str, encoding: str = 'utf-8') -> Any:
    """从 JSON 文件中读取并解析数据。

    Args:
        file_path: JSON 文件路径。
        encoding: 文件编码，默认为 'utf-8'。

    Returns:
        解析后的 JSON 数据（dict、list、str、int、float、bool 或 None）。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        return json.load(f)


def load_from_str(json_str: str) -> Any:
    """从 JSON 字符串中解析数据。

    Args:
        json_str: JSON 格式的字符串。

    Returns:
        解析后的 JSON 数据（dict、list、str、int、float、bool 或 None）。
    """
    return json.loads(json_str)
