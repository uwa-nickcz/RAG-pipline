# -*- coding: utf-8 -*-
# @Time    : 2025/4/9 16:20
# @Author  : cz
# @File    : config.py
# @Software: PyCharm
import os


model_cache_path = os.getenv("MODELSCOPE_CACHE", r"D:\workspace\数字人\backend\metahuman-backend-asr")
HOST_IP = "172.26.1.35"
ORACLE_IP = "172.26.1.75"
# 数据库配置
PG_DATABASE_URL = f"postgresql+psycopg2://root:Password123%40postgres@{HOST_IP}:5432/maxkb"
PG_DATABASE_DICT = {"host":HOST_IP,
                    "port":5432,
                    "dbname":"maxkb",
                    "user":"root",
                    "password":"Password123@postgres"
                   }

config = {"model": "Qwen3-30B-A3B-FP8",
          "api_key": "EMPTY",
          "api_url": f"http://{HOST_IP}:8001/v1/chat/completions",
          "collection_name": "test",
          "dsn": f'{ORACLE_IP}:1521/orcl',
          "user": 'itps_lz_dev',
          "password": 'itps_lz_dev',
          "code_mode":"",
          "code_mode_url":""}

EMBEDDING_DIM = 1024
# 模型部署框架
FRAMEWORK = "vllm"
# 模型名称
# MODEL = "deepseek-r1:70b"
MODEL = "Qwen3-30B-A3B-FP8"
# Ollama Embedding API 的基础 URL
OLLAMA_API_URL = f"http://{HOST_IP}/api/model/42f63a3d-427e-11ef-b3ec-a8a1595801ab/embed_query"

# llm API 的基础 URL
LLM_API_URL = f"http://{HOST_IP}:8001/v1/chat/completions"

# LLM_API_URL = "http://172.16.98.1:11434/api/generate"

#适配openai的llm api
OPENAI_API_URL = f"http://{HOST_IP}:8001/v1"

DeptNoYinchuan = '1641'
UPLOAD_IP = '172.26.1.89'
UPLOAD_PORT = '9527'
FILE_AGENT_IP = HOST_IP
FILE_AGENT_PORT = '8881'

MAXKB_login = f"http://{HOST_IP}/api/user/login"
MAXKB_INFO = {
              "username": "admin",
              "password": "cdtye_2025"
             }
MAXKB_SEARCH = f"http://{HOST_IP}:8080/api/dataset/4bdb5df4-1372-11f0-92b8-0242ac120003/hit_test"

MAXKB_APP_OPEN = f"http://{HOST_IP}/api/application/a67a5d02-84b3-11f0-8f9c-0242ac150003/chat/open"
MAXKB_APP_CHAT = f"http://{HOST_IP}/api/application/chat_message/"
MAXKB_APP_HEARDER = "application-6f6affc79428cbda0eee3555464980f5"

ORACLEDB_DEVICE= os.getenv("ORACAL_DRIVERS", 'E:\instantclient\instantclient_23_8')
# ORACLEDB_DEVICE = "/usr/local/webapps/mcp/instantclient_23_8"
CUDA_VISIBLE_DEVICES=os.getenv("CUDA_VISIBLE_DEVICES", '0')
