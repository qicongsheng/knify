#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: qicongsheng
from setuptools import setup, find_packages
from knify import help

setup(
    name=help.get_pip_name(),
    version=help.get_version(),
    keywords=help.get_pip_name(),
    description='Development tools for python',
    license='MIT License',
    url='https://github.com/qicongsheng/%s' % help.get_pip_name(),
    author='qicongsheng',
    author_email='qicongsheng@outlook.com',
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'loguru>=0.7.2',
        'urllib3>=1.26.9'
    ]
)
