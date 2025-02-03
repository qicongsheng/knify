#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from setuptools import setup, find_packages

from knify import help

setup(
    name=help.get_name(),
    version=help.get_version(),
    keywords=help.get_name(),
    description='Development tools for python',
    license='MIT License',
    url='https://github.com/qicongsheng/%s' % help.get_name(),
    author='qicongsheng',
    author_email='qicongsheng@outlook.com',
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'loguru',
        'urllib3',
        'openpyxl',
        'pytz',
        'requests'
    ]
)
