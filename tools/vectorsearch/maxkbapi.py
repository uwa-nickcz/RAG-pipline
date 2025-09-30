# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/8/5 13:11
# @File     : maxkbapi.py
# @contact  ： ***
import requests
from urllib.parse import quote
from langchain.tools import tool
from config import MAXKB_SEARCH,MAXKB_INFO,MAXKB_login,MAXKB_APP_OPEN
@tool
def databasesearch(query_text:str)->str:
    """
    用于查询大铁作业准则等信息。
    参数:
    query_text (str): 用户问题
    """
    token_url = MAXKB_login
    token = requests.post(
        token_url,
        json=MAXKB_INFO,
        timeout=10  # 设置超时时间
    )
    sim_threshold = 0.4
    top_n = 5
    mode = "embedding"
    api_key = token.json().get('data')


    base_url = MAXKB_SEARCH

    # 对查询文本进行 URL 编码
    encoded_query = quote(query_text, encoding='utf-8')

    # 构造完整 URL
    url = f"{base_url}?query_text={encoded_query}&similarity={sim_threshold}&top_number={top_n}&search_mode={mode}"

    # 设置请求头 (Key-Value 鉴权)
    headers = {
        "Authorization": f"{api_key}",  # 常见的鉴权方式
        # 或者如果使用自定义头:
        # "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    try:
        # 发送 GET 请求
        response = requests.get(
            url,
            headers=headers,
            timeout=10  # 设置超时时间
        )

        # 检查响应状态
        response.raise_for_status()
        result = response.json()

        if result['message'] == '成功' or len(result['data']) != 0:
            return '\n\n'.join([chunk['content'] for chunk in result['data']])
        # 返回 JSON 响应
        return None

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

def get_chat_id():
    """
    用于查询大铁作业准则等信息。
    参数:
    query_text (str): 用户问题
    """
    token_url = MAXKB_login
    token = requests.post(
        token_url,
        json=MAXKB_INFO,
        timeout=10  # 设置超时时间
    )
    api_key = token.json().get('data')
    headers = {
        "Authorization": f"{api_key}",  # 常见的鉴权方式
        # 或者如果使用自定义头:
        # "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    chat_id = requests.get(MAXKB_APP_OPEN,headers=headers).json().get('data')
    return chat_id

# 使用示例
if __name__ == "__main__":
    print(get_chat_id())