# -*- coding: utf-8 -*-
"""
@Project   : vannaai
@File      : vanna_tool.py
@Author    : Cz
@Contact   : chenzhu@cdtye.com
@Created   : 2025/7/3 10:42
"""
import sys

from sympy import false

sys.path.append("../")

# from data import DDL,lanzhou_vision
from data_loader.data_loader import split_sql_statements
from llm.qwen_vllm import Vllmqwen
from vector_store.storeinpostgre import PostgreSQLVectorDB
from pydantic import BaseModel,Field, SecretStr, AnyUrl, conint, constr
from typing import Literal, Optional, Dict
from vanna.flask import VannaFlaskApp
import threading
from tools.sqlsearch.vannaer import Vannaer
import oracledb
oracledb.init_oracle_client(lib_dir=r"E:\instantclient\instantclient_23_8")

class MyVanna(PostgreSQLVectorDB, Vllmqwen):
    def __init__(self, config=None,collection_name=None):
        PostgreSQLVectorDB.__init__(self, config=config,collection_name=collection_name)
        Vllmqwen.__init__(self, config=config)


# class Params(BaseModel):
#     api_url: AnyUrl = Field(..., description="API 服务端点 URL")
#     api_key: SecretStr = Field(..., description="API 访问密钥", exclude=True)  # 敏感字段自动排除
#     model: str = Field("gpt-3.5-turbo", description="使用的AI模型")
#     host: constr(strip_whitespace=True, min_length=1) = Field("localhost", description="数据库主机地址")
#     port: conint(ge=1, le=65535) = Field(3306, description="数据库端口号")
#     dbname: constr(min_length=1) = Field(..., description="数据库名称")
#     user: constr(min_length=1) = Field(..., description="数据库用户名")
#     password: SecretStr = Field(..., description="数据库密码", exclude=True)  # 敏感字段自动排除

class DBTool(Vannaer):
    # 类变量缓存连接对象 {参数签名: 连接实例}
    _connection_cache = {}

    def __init__(self, conn_params:Dict,ddl=None,document=None,sql=None):
        self.conn_params = conn_params
        self.ddl = ddl
        self.document = document
        self.sql = sql
        self._signature = self._create_signature(conn_params)

        # 如果已有相同参数的连接，则复用
        if self._signature not in DBTool._connection_cache:
            self._create_connection()
        else:
            self.connection = DBTool._connection_cache[self._signature]

    def _create_signature(self, params):
        """生成连接参数唯一签名"""
        return tuple(sorted(params.items()))  # 将参数字典转为可哈希元组

    def _create_connection(self):
        self.vn = MyVanna(config=self.conn_params,collection_name=self.conn_params['collection_name'])
        if self.conn_params['dialect'].lower() == "postgresql":
            self.vn.connect_to_postgres(host=self.conn_params["host"], dbname=self.conn_params["dbname"], user=self.conn_params["user"], password=self.conn_params["password"],
                               port=self.conn_params["port"])
        elif self.conn_params['dialect'].lower() == "mysql":
            self.vn.connect_to_mysql(host=self.conn_params["host"], dbname=self.conn_params["dbname"], user=self.conn_params["user"], password=self.conn_params["password"],
                               port=int(self.conn_params["port"]))
        elif self.conn_params['dialect'].lower() == "oracle":
            self.vn.connect_to_oracle(dsn=self.conn_params.get("dsn",None), user=self.conn_params["user"], password=self.conn_params["password"])
        else:
            raise ValueError(f"{self.conn_params['dialect']} is not supported.")

        if self.conn_params.get('is_train',None):
            if self.conn_params['is_train'].lower() == "true":
                self.train(ddl=self.ddl,documentation=self.document,sql=self.sql)

            DBTool._connection_cache[self._signature] = self.vn

    def execute_query(self, sql):
        return_data = self.conn_params.get("return_data",None)
        if return_data is None:
            return DBTool._connection_cache[self._signature].ask(question=sql)

        if return_data == "fig" or return_data == 'all':
            sql, df, fig = DBTool._connection_cache[self._signature].ask(question=sql,visualize=True)
        else:
            sql, df, fig = DBTool._connection_cache[self._signature].ask(question=sql,visualize=False)
        if return_data == "sql":
            return sql
        elif return_data == "df":
            return df.to_markdown(index=False)
        elif return_data == "fig":
            return  "<html_rander>"+fig.to_html(full_html=True, include_plotlyjs='cdn')+"</html_rander>"
        else:
            try:
                return [sql, df, "<html_rander>"+fig.to_html(full_html=True, include_plotlyjs='cdn')+"</html_rander>"]
            except:
                return [sql, df, None]





    # def __del__(self):
    #     """对象销毁时清理缓存（可选）"""
    #     if self._signature in DBTool._connection_cache:
    #         del DBTool._connection_cache[self._signature]






if __name__ == "__main__":
    config = {"model": "Qwen3-30B-A3B-FP8", "api_key": "EMPTY"}
    vn = MyVanna(config=config)
    vn.connect_to_postgres(host='127.0.0.1', dbname='maxkb', user='root', password='Password123@postgres', port='5432')
    for ddl in ["DDL"]:
        vn.train(ddl=ddl)
    vn.ask(question="请问与轨道交通相关的应用有多少个，他们的具体功能是什么")
    print(vn.get_training_data())
    # from vanna.flask import VannaFlaskApp
    # VannaFlaskApp(vn).run()