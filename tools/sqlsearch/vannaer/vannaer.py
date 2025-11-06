# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/28 16:54
# @File     : vannaer.py
# @contact  ： ***
import sys
sys.path.append("../../../")
from data.input.vanna_train.ddl import LANGZHOU_VISION
from data_loader.data_loader import split_sql_statements
from llm.qwen_vllm import Vllmqwen
from vector_store.storeinpostgre import PostgreSQLVectorDB
from tqdm import tqdm
import oracledb
from config import ORACLEDB_DEVICE
from config import config

oracledb.init_oracle_client(lib_dir=ORACLEDB_DEVICE)
class MyVanna(PostgreSQLVectorDB, Vllmqwen):
    def __init__(self, config=None,collection_name=None):
        PostgreSQLVectorDB.__init__(self, config=config,collection_name=collection_name)
        Vllmqwen.__init__(self, config=config)


class Vannaer():
    def __init__(self, config=None,collection_name=None):
        self.config = config
        self.vn = MyVanna(config=config,collection_name=config["collection_name"])
        self.vn.connect_to_oracle(dsn=config['dsn'], user=config['user'], password=config['password'])

    def train(self, question=None,ddl=None, documentation=None,sql=None,app_id=None):
        if ddl:
            if isinstance(ddl, list):
                for dl in ddl:
                    self.vn.train(ddl=dl,app_id=app_id)
            elif isinstance(ddl, str):
                self.vn.train(ddl=ddl,app_id=app_id)

        if documentation:
            if isinstance(documentation, list):
                for document in documentation:
                    self.vn.train(documentation=document,app_id=app_id)
            elif isinstance(documentation, str):
                self.vn.train(documentation=documentation,app_id=app_id)

        if sql:
            self.vn.train(question=question,sql=sql,app_id=app_id)

    def ask(self, question=None, allow_llm_to_see_data=True, auto_train=False,visualize=True):
        sql, df, fig = self.vn.ask(question=question, allow_llm_to_see_data=allow_llm_to_see_data, auto_train=auto_train,visualize=visualize,print_results = False)
        return sql,df,fig


if __name__ == "__main__":

    lanzhou = Vannaer(config=config)

    try:
        with open(r"D:\workspace\RAG-pipline\data\input\vanna_train\documents_lanzhou.txt",'r',encoding='utf-8') as f:
            documents = f.read().split("#@")
    except:
        documents = None
    lanzhou.train(ddl=LANGZHOU_VISION,documentation=documents)

    # question = ["统计本年度各个线路中一共有多少缺陷","2025年4月9日当天的缺陷有多少"]
    # lanzhou.ask(question=question[0],allow_llm_to_see_data=True,auto_train=False)


    # from vanna.flask import VannaFlaskApp
    # VannaFlaskApp(vn).run()

