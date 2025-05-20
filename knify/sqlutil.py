#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
import json
import re

from knify import excelutil


def generate_sql_from_excel(excel_file, sql_template, filter_func=None, preprocess_func=None, postprocess_func=None,
                            header_row=1,
                            sheet_index=0, translate_chars=None):
    def replace_placeholders(template, values):
        def replace_match(match):
            key = match.group(1)
            return str(values.get(key, match.group(0)))

        return re.sub(r'\$\{(.*?)\}', replace_match, template)

    def process_row_data(row_data):
        for key, value in row_data.items():
            # 处理空值
            if value is None or (isinstance(value, str) and value.strip() == ''):
                row_data[key] = "NULL"
            # 转义
            if translate_chars is not None and isinstance(value, str):
                for trans_key, trans_value in translate_chars.items():
                    row_data[key] = row_data[key].replace(trans_key, trans_value)
        return replace_placeholders(sql_template, row_data).replace('"NULL"', 'NULL').replace("'NULL'", 'NULL')

    return excelutil.process_data(excel_file, process_row_data, filter_func, preprocess_func, postprocess_func,
                                  header_row, sheet_index)


def generate_sql_from_json(json_data, sql_template, filter_func=None, preprocess_func=None, postprocess_func=None,
                           translate_chars=None):
    def replace_placeholders(template, values):
        def replace_match(match):
            key = match.group(1)
            return str(values.get(key, match.group(0)))

        return re.sub(r'\$\{(.*?)\}', replace_match, template)

    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    result = []
    for row_data in json_data:

        # 如果提供了预处理函数，则对列数据进行处理
        if preprocess_func:
            row_data = preprocess_func(row_data)

        # 如果提供了过滤函数，并且过滤函数返回True，则跳过该行
        if filter_func and filter_func(row_data):
            continue
        for key, value in row_data.items():
            # 处理空值
            if value is None or (isinstance(value, str) and value.strip() == ''):
                row_data[key] = "NULL"
            # 转义
            if translate_chars is not None and isinstance(value, str):
                for trans_key, trans_value in translate_chars.items():
                    row_data[key] = row_data[key].replace(trans_key, trans_value)
        sql_ = replace_placeholders(sql_template, row_data).replace('"NULL"', 'NULL').replace("'NULL'", 'NULL')
        # 如果提供了后置处理函数，则对生成的结果进行处理
        if postprocess_func:
            sql_ = postprocess_func(sql_, row_data)

        result.append(sql_)
    return result
