# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 11:27
# @File     : __init__.py.py
# @contact  ： ***
from tools.sqlsearch.vannaer import Vannaer
from config import config

lanzhou = Vannaer(config=config)

# with open(r"D:\workspace\vannaai\src\data\documents_lanzhou.txt",'r',encoding='utf-8') as f:
#     documents = f.read().split("#@")
# lanzhou.train(ddl=split_sql_statements(lanzhou_vision[0]),documentation=documents)

# question = ["统计本年度各个线路中一共有多少缺陷,过滤掉线路为空的数据","2025年4月9日当天的缺陷有多少"]
# lanzhou.ask(question=question[0],allow_llm_to_see_data=True,auto_train=False)
# from vanna.flask import VannaFlaskApp
# VannaFlaskApp(vn).run()

def sqlsearch(query:str):
    """
    用于在数据库中查询缺陷信息
    入参：
        query：用户问题，请直接传入用户问题
    """
    return lanzhou.ask(question=query,allow_llm_to_see_data=True,auto_train=False,visualize=False)