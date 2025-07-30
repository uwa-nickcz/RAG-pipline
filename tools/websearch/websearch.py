# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/24 16:21
# @File     : websearch.py
# @contact  ： ***
# Define a tool that searches the web for information.
# For simplicity, we will use a mock function here that returns a static string.
import requests
async def web_search(query: str) -> str:
    # Replace this with an actual web search function
    # For example, you could use a web search API or a search engine like Google.
    return "AutoGen is a programming framework for building multi-agent applications."


# SearxNG搜索函数
def web_search(query:str, top_k:int = 5):
    """Find information on the web"""
    searxng_url = 'http://172.26.1.35:9311/search'  # 替换为你的SearxNG实例URL
    params = {
        'q': query,
        'format': 'json',
        'engines': ["baidu"]

    }
    response = requests.get(searxng_url, params=params)
    response.raise_for_status()

    search_texts = [result['title'] + "\n" + result['content'] for result in response.json()['results']]
    if top_k < len(search_texts):
        return search_texts
    if top_k >= len(search_texts):
        return search_texts[:top_k]