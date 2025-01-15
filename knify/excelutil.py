#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from typing import Callable

from openpyxl.reader.excel import load_workbook

from . import listutil
from . import objutil


class Header:
    def __init__(self, index: int, name: str | None, transformer: Callable[[object], object] = None):
        self.index = index
        self.name = name
        self.transformer = transformer


class HeaderBuilder:
    def __init__(self):
        self.default_transformer = None
        self.headers = []

    def set_default_transformer(self, transformer: Callable[[object], object] = None) -> object:
        self.default_transformer = transformer
        return self

    def set_names(self, names: list[str] = None) -> object:
        for index_, name in enumerate(names):
            self.headers.append(Header(index_, name, self.default_transformer))
        return self

    def set_transformer(self, name: str, transformer: Callable[[object], object] = None) -> object:
        for header in self.headers:
            if name == header.name:
                header.transformer = transformer
        return self

    def append(self, index: int, name: str | None, transformer: Callable[[object], object] = None) -> object:
        target_index = objutil.default_if_none(index, len(self.headers))
        target_transformer = objutil.default_if_none(transformer, self.default_transformer)
        self.headers.append(Header(target_index, name, target_transformer))
        return self

    def to_headers(self) -> list[Header]:
        return self.headers


def read_excel(file_path: str, sheet: str | int | None = 0, headers: list[Header] | None = None, start_row: int = 1,
               header_row: int = 0) -> list[object]:
    results = []
    workbook = load_workbook(filename=file_path)
    sheet_ = workbook[sheet] if isinstance(sheet, str) else workbook[workbook.sheetnames[sheet]]
    headers_ = [cell.value for cell in sheet_[header_row + 1]]
    for row_idx, row in enumerate(sheet_.rows):
        if row_idx < start_row:
            continue
        result = {}
        for header_idx, header_ in enumerate(headers_):
            # 没有传入headers,使用默认header
            if listutil.is_empty(headers):
                result[header_] = row[header_idx].value
            # 传入了headers
            else:
                header = listutil.find_first(list(filter(lambda h_: h_.index == header_idx, headers)))
                if header is None:
                    continue
                else:
                    col_name = objutil.default_if_none(header.name, header_)
                    cell_value = row[header_idx].value
                    cell_value = cell_value if header.transformer is None else header.transformer(row[header_idx].value)
                    result[col_name] = cell_value
        if objutil.has_keys(result):
            results.append(result)
    return results


def read_headers(file_path: str, sheet: str | int | None = 0, header_row: int = 0):
    workbook = load_workbook(filename=file_path)
    sheet_ = workbook[sheet] if isinstance(sheet, str) else workbook[workbook.sheetnames[sheet]]
    return [cell.value for cell in sheet_[header_row + 1]]
