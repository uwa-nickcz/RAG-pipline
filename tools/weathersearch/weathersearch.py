# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/24 17:09
# @File     : weathersearch.py
# @contact  ： ***
import requests


def weathersearch(city:str):
    api_key = "你的API_KEY"
    url = f"https://www.tianqiapi.com/api?version=v1&city={city}"
    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        return data
    else:
        print("城市未找到或API错误")


