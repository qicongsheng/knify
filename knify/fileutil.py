#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng


def read_to_string(file_path_: str, encoding_: str = 'utf-8') -> str:
    with open(file_path_, 'r', encoding=encoding_) as file:
        content = file.read()
        return content


def read_lines(file_path_: str, encoding_: str = 'utf-8') -> list[str]:
    with open(file_path_, 'r', encoding=encoding_) as file:
        return file.readlines()
