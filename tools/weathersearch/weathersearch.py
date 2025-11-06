# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/24 17:09
# @File     : weathersearch.py
# @contact  ： ***
import requests
from langchain_core.tools import tool

@tool
def weathersearch(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"{city}的天气是晴朗的，25°C"