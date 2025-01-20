#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
def read_to_string(file_path: str, encoding: str = 'utf-8') -> str:
    with open(file_path, 'r', encoding=encoding) as file:
        return file.read()


def read_lines(file_path: str, encoding: str = 'utf-8', trim: bool = True) -> list[str]:
    with open(file_path, 'r', encoding=encoding) as file:
        return [line_.strip() for line_ in file.readlines()] if trim else file.readlines()


def write_line(file_path: str, line: str, encoding: str = 'utf-8', append: bool = True) -> None:
    mode = 'a' if append else 'w'
    with open(file_path, mode, encoding=encoding) as file:
        file.write(str(line) + '\n')


def write_lines(file_path: str, lines: list[object], encoding: str = 'utf-8', append: bool = True) -> None:
    mode = 'a' if append else 'w'
    with open(file_path, mode, encoding=encoding) as file:
        file.writelines([str(line) + '\n' for line in lines])
