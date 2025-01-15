#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from typing import Callable

from openpyxl.reader.excel import load_workbook


class Header:
    def __init__(self, index: int, name: str | None, transformer: Callable[[object], object] = None):
        self.index = index
        self.name = name
        self.transformer = transformer


class HeaderBuilder:
    def __init__(self):
        self.default_transformer = None
        self.headers = []

    def set_default_transformer(self, transformer: Callable[[object], object] = None):
        self.default_transformer = transformer
        return self

    def set_names(self, names: list[str] = None):
        for index_, name in enumerate(names):
            self.headers.append(Header(len(self.headers), name, self.default_transformer))
        return self

    def set_transformer(self, name: str, transformer: Callable[[object], object] = None):
        for header in self.headers:
            if name == header.name:
                header.transformer = transformer
        return self

    def append(self, index: int, name: str | None, transformer: Callable[[object], object] = None):
        target_tindex = index if index is not None else len(self.headers)
        target_transformer = transformer if transformer is not None else self.default_transformer
        self.headers.append(Header(target_tindex, name, target_transformer))
        return self

    def to_headers(self):
        return self.headers


def read_excel(file_path: str, sheet: str | int | None = 0, headers: list[Header] | None = None, start_row: int = 1):
    results = []
    workbook = load_workbook(filename=file_path)
    sheet_ = workbook[sheet] if isinstance(sheet, str) else workbook[workbook.sheetnames[sheet]]
    headers_ = [cell.value for cell in sheet_[1]]
    for row_idx, row in enumerate(sheet_.rows):
        if row_idx < start_row:
            continue
        result = {}
        for header_idx, header_ in enumerate(headers_):
            # 没有传入headers,使用默认header
            if headers is None or len(headers) == 0:
                result[header_] = row[header_idx].value
            # 传入了headers
            else:
                target_headers = list(filter(lambda h_: h_.index == header_idx, headers))
                header = target_headers[0] if target_headers is not None and len(target_headers) > 0 else None
                if header is None:
                    continue
                else:
                    col_name = header.name if header.name is not None else header_
                    cell_value = row[header_idx].value
                    cell_value = cell_value if header.transformer is None else header.transformer(row[header_idx].value)
                    result[col_name] = cell_value
        if len(result.keys()) > 0:
            results.append(result)
    return results
