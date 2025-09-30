"""
主应用程序入口 - 重构后的RAG Pipeline系统

使用模块化设计，提供更好的代码组织和维护性
"""
import sys
import os
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from config.config import APP_HOST, APP_PORT

# 导入路由模块
from app.routers import file_server, asr_server, pgsql_server, tts_server
from app.routers.agent_server import router as agent_router

# 导入核心组件
from app.core.heartbeat import global_heartbeat_manager
from logger import logger

# 设置CUDA设备
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# 创建FastAPI应用实例
app = FastAPI(
    title="RAG Pipeline API",
    description="重构后的检索增强生成系统，提供智能问答、语音识别、文档处理等功能",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(file_server.router, prefix="/file", tags=["文件服务"])
app.include_router(asr_server.router, prefix="/asr", tags=["语音识别"])
app.include_router(agent_router, tags=["智能体服务"])
app.include_router(pgsql_server.router, prefix="/pgsql", tags=["数据库服务"])
app.include_router(tts_server.router, prefix="/tts", tags=["语音合成"])


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("RAG Pipeline 系统启动中...")
    
    # 启动全局心跳管理器
    await global_heartbeat_manager.start()
    logger.info("心跳管理器已启动")
    
    logger.info("RAG Pipeline 系统启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("RAG Pipeline 系统关闭中...")
    
    # 停止全局心跳管理器
    await global_heartbeat_manager.stop()
    logger.info("心跳管理器已停止")
    
    logger.info("RAG Pipeline 系统已关闭")


@app.get("/")
async def root() -> Dict[str, Any]:
    """
    根路径接口 - 返回系统状态信息
    
    Returns:
        系统状态和基本信息
    """
    return {
        "message": "RAG Pipeline API 系统运行正常",
        "version": "2.0.0",
        "status": "healthy",
        "features": [
            "智能问答",
            "语音识别", 
            "文档处理",
            "数据库查询",
            "语音合成"
        ],
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查接口
    
    Returns:
        系统健康状态
    """
    # 获取心跳管理器统计信息
    heartbeat_stats = global_heartbeat_manager.get_monitor().get_connection_stats()
    
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "system": {
            "python_version": sys.version,
            "platform": sys.platform
        },
        "connections": heartbeat_stats,
        "services": {
            "agent_service": "running",
            "streaming_service": "running",
            "heartbeat_monitor": "running"
        }
    }


if __name__ == "__main__":
    import uvicorn
    import time
    
    # 从配置文件读取主机和端口，如果未定义则使用默认值
    host = getattr(config, "APP_HOST", "0.0.0.0") if 'config' in globals() else "0.0.0.0"
    port = getattr(config, "APP_PORT", 8888) if 'config' in globals() else 8888
    
    logger.info(f"启动服务器: http://{host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )