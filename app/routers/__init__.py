# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 16:22
# @File     : __init__.py.py
# @contact  ： ***
from app.routers.agent_server_refactored import router as agent_backend_router
from app.routers.asr_server import router as asr_router
# from app.routers.file_server import router as file_router
from app.routers.pgsql_server import router as pgsql_router
