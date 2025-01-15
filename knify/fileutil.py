#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng


def read_to_string(file_path_: str, encoding_: str = 'utf-8') -> str:
    with open(file_path_, 'r', encoding=encoding_) as file:
        return file.read()


def read_lines(file_path_: str, encoding_: str = 'utf-8', trim: bool = True) -> list[str]:
    with open(file_path_, 'r', encoding=encoding_) as file:
        return [line_.strip() for line_ in file.readlines()] if trim else file.readlines()
