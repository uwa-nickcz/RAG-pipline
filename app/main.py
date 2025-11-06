# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 16:18
# @File     : main.py
# @contact  ： ***
# main.py
import sys
import os
sys.path.append("../")
from fastapi import FastAPI
from app.routers import file_server, asr_server,agent_backend_router,pgsql_server
from config import CUDA_VISIBLE_DEVICES
app = FastAPI(title="统一服务接口", version="1.0")
os.environ["CUDA_VISIBLE_DEVICES"] = CUDA_VISIBLE_DEVICES
# 注册路由
app.include_router(file_server.router)
app.include_router(asr_server.router)
app.include_router(agent_backend_router)
app.include_router(pgsql_server.router)

@app.get("/")
async def root():
    return {
        "message": "统一服务接口已启动",
        "routes": {
            "/files": "文件服务",
            "/asr": "语音识别服务",
            "/agent": "智能体服务已启动",
            "/pgqsl": "数据库服务已启动",
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.112.228", port=8880)