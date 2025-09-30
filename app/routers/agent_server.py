# -*- coding: utf-8 -*-
"""
重构后的智能体服务路由模块

使用模块化设计，提供更稳定的流式接口和心跳机制
"""
import json
import asyncio
import time
from typing import Optional, List, Dict, Any, Union
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor

import httpx
from agents.agent import (
    agent_executor_web,
    agent_executor_for_metahuman,
    agent_executor_for_v3,
    chain
)
from tools import sql_train
from tools import sqlsearch, databasesearch, generate_report
from tools.vectorsearch.maxkbapi import get_chat_id
from prompt import AGENT_PROMPT_V3
from config import MAXKB_APP_CHAT, MAXKB_APP_HEARDER

# 导入新的模块化组件
from app.core.streaming import HeartbeatConfig
from app.core.events import UnifiedEventManager, CallbackBasedEventGenerator
from app.core.callbacks import StreamingCallbackHandler, EnhancedStreamingCallbackHandler
from app.services.streaming_service import StreamingService, AdvancedStreamingService
from app.services.agent_service import AgentService

# 加载环境变量
load_dotenv()

# 创建路由器
router = APIRouter(
    prefix="/agent",
    tags=["智能体服务"],
    responses={
        404: {"description": "未找到资源"},
        500: {"description": "服务器内部错误"}
    }
)

# 初始化服务
heartbeat_config = HeartbeatConfig(
    interval=15.0,
    timeout_threshold=300,
    progress_interval=30.0
)
streaming_service = AdvancedStreamingService(heartbeat_config)
agent_service = AgentService()

# 创建全局线程池
executor = ThreadPoolExecutor(max_workers=10)
plotly_executor = ThreadPoolExecutor(max_workers=40, thread_name_prefix="plotly_worker")


class OpenAIMessage(BaseModel):
    """OpenAI兼容的消息格式"""
    role: str = Field(..., description="消息角色，如user、assistant、system")
    content: str = Field(..., description="消息内容")


class OpenAIRequest(BaseModel):
    """OpenAI兼容的请求格式"""
    model: str = Field("Qwen3-30B-A3B-FP8", description="使用的模型名称")
    messages: List[OpenAIMessage] = Field(..., description="消息历史")
    stream: bool = Field(False, description="是否使用流式响应")
    temperature: float = Field(0.5, description="温度参数，控制随机性")
    max_tokens: int = Field(15000, description="最大生成token数")
    max_iterations: int = Field(5, description="智能体最大迭代次数")


class TrainData(BaseModel):
    """SQL训练数据模型"""
    question: Optional[str] = Field(None, description="问题")
    ddl: Optional[str] = Field(None, description="数据定义语言")
    documentation: Optional[str] = Field(None, description="文档")
    sql: Optional[str] = Field(None, description="SQL查询")


@router.post("/train")
async def train_sql(request: TrainData):
    """训练SQL模型"""
    try:
        sql_train(
            question=request.question,
            ddl=request.ddl,
            documentation=request.documentation,
            sql=request.sql
        )
        return {"code": 200, "message": "训练成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")


@router.post("/v1/chat/completions/no_steam",
          response_description="非流式智能体查询响应",
          status_code=200,
          responses={
              400: {"description": "无效的请求参数"},
              500: {"description": "服务器内部错误"}
          })
async def agent_query_non_streaming(request: OpenAIRequest):
    """
    执行智能体查询 - 非流式版本，返回OpenAI兼容格式的完整响应
    
    Args:
        request: 包含消息和模型信息的请求对象
        
    Returns:
        Dict: OpenAI兼容的响应格式，包含智能体执行详情
        
    Raises:
        HTTPException: 当没有找到用户消息或执行失败时
    """
    # 提取用户消息
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")

    input_text = user_messages[-1].content
    max_iterations = request.max_iterations or 5

    # 执行智能体
    result = await agent_service.execute_agent(
        input_text=input_text,
        executor_type="metahuman",
        max_iterations=max_iterations
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    # 生成响应ID和时间戳
    response_id = f"chatcmpl-{int(time.time())}"
    created_timestamp = int(time.time())
    
    # 计算token数量（简化估算）
    input_tokens = len(input_text)
    output_tokens = len(result.output)
    
    # 返回OpenAI兼容格式
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": created_timestamp,
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result.output
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        },
        "agent_details": {
            "input": input_text,
            "steps": [step.__dict__ for step in result.steps],
            "execution_time": result.execution_time
        }
    }


@router.post("/v1/chat/completions",
          response_description="流式智能体查询响应",
          status_code=200,
          responses={
              400: {"description": "无效的请求参数"},
              500: {"description": "服务器内部错误"}
          })
async def agent_query_streaming(request: OpenAIRequest):
    """
    流式执行智能体查询 - 返回OpenAI兼容的SSE格式响应
    
    Args:
        request: 包含消息和模型信息的请求对象
        
    Returns:
        StreamingResponse: 服务器发送事件流，包含智能体执行过程和结果
    """
    # 提取用户消息
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        return await streaming_service.create_error_stream_response(
            error_message="No user message found",
            model=request.model
        )

    input_text = user_messages[-1].content
    max_iterations = request.max_iterations or 5

    try:
        return await streaming_service.create_monitored_stream_response(
            input_text=input_text,
            model=request.model,
            executor_type="metahuman",
            max_iterations=max_iterations
        )
    except Exception as e:
        return await streaming_service.create_error_stream_response(
            error_message=f"执行失败: {str(e)}",
            model=request.model
        )


@router.post("/v2/chat/completions")
async def agent_query_streaming_web(request: OpenAIRequest):
    """
    流式执行智能体查询 - Web版本
    
    使用web执行器，适用于网络搜索等场景
    """
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        return await streaming_service.create_error_stream_response(
            error_message="No user message found",
            model=request.model
        )

    input_text = user_messages[-1].content
    max_iterations = request.max_iterations or 5

    try:
        return await streaming_service.create_monitored_stream_response(
            input_text=input_text,
            model=request.model,
            executor_type="web",
            max_iterations=max_iterations
        )
    except Exception as e:
        return await streaming_service.create_error_stream_response(
            error_message=f"执行失败: {str(e)}",
            model=request.model
        )


@router.post("/v3/chat/completions")
async def enhanced_chat_completion(request: OpenAIRequest):
    """
    增强版流式聊天完成接口 - 使用统一事件管理器
    
    支持特殊指令处理：[power_knowledge]、[query_data]、[generate_report]
    使用统一的事件处理机制，整合回调和直接事件
    """
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        return await streaming_service.create_error_stream_response(
            error_message="No user message found",
            model=request.model
        )

    input_text = user_messages[-1].content
    
    # 生成唯一的ID
    request_id = f"chatcmpl-{int(time.time())}"
    created_time = int(time.time())
    
    # 创建统一事件管理器
    event_manager = UnifiedEventManager(request_id, request.model)

    async def enhanced_event_generator():
        """增强版事件生成器，使用统一事件管理机制"""
        
        # 发送初始响应
        yield event_manager.create_direct_event("initial")

        # 检查是否包含power_knowledge指令
        if '[power_knowledge]' in input_text.lower():
            # 发送处理提示
            chat_id = get_chat_id()
            yield event_manager.create_direct_event("token", content=" ")
            
            async with httpx.AsyncClient() as client:
                # 调用流式接口
                headers = {}
                headers["Authorization"] = MAXKB_APP_HEARDER
                payload = {"message": input_text}
                async with client.stream("POST",
                                         MAXKB_APP_CHAT+chat_id,
                                         json=payload,
                                         headers=headers) as response:

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk

                        # 按行处理 SSE 格式
                        while '\n' in buffer:
                            lines = buffer.split('\n')
                            buffer = lines[-1]  # 保留最后一个不完整的行

                            for line in lines[:-1]:
                                line = line.strip()
                                if line.startswith('data: '):
                                    # 直接转发完整的 SSE 行
                                    try:
                                        chunk_text = json.loads(line[6:])["reasoning_content"] if json.loads(line[6:])["reasoning_content"] else json.loads(line[6:])["content"]
                                        yield event_manager.create_direct_event("token", content=chunk_text)
                                    except Exception as e:
                                        yield event_manager.create_direct_event("finish")
                                        yield event_manager.create_direct_event("done")
                                        return
        # 处理其他特殊指令
        processed_input = await _process_special_commands(
            input_text, request_id, created_time, request.model
        )
        
        # 如果处理过程中已经生成了完整响应，直接返回
        if processed_input is None:
            return
        
        # 开始LLM流式响应
        try:
            async for chunk in chain.astream({"input": processed_input}):
                if content := chunk.content:
                    yield event_manager.create_direct_event("token", content=content)

        except Exception as e:
            yield event_manager.create_direct_event("error", error=str(e))

        # 发送结束标记
        yield event_manager.create_direct_event("finish")
        yield event_manager.create_direct_event("done")

    return StreamingResponse(
        enhanced_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def _process_special_commands(
    input_text: str,
    request_id: str,
    created_time: int,
    model: str
) -> Optional[str]:
    """
    处理特殊指令
    
    Args:
        input_text: 输入文本
        request_id: 请求ID
        created_time: 创建时间
        model: 模型名称
        
    Returns:
        处理后的输入文本，如果返回None表示已经完成响应
    """
    # power_knowledge指令现在在enhanced_event_generator中直接处理
    if '[query_data]' in input_text.lower():
        return await _handle_query_data(input_text)
    elif '[generate_report]' in input_text.lower():
        return await _handle_generate_report(input_text)
    else:
        return input_text


async def _handle_power_knowledge_stream(
    input_text: str,
    request_id: str,
    created_time: int,
    model: str,
    event_manager: UnifiedEventManager
):
    """处理power_knowledge指令的流式版本"""
    try:
        chat_id = get_chat_id()
        headers = {"Authorization": MAXKB_APP_HEARDER}
        payload = {"message": input_text.replace('[power_knowledge]', '').strip()}
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                MAXKB_APP_CHAT + chat_id,
                json=payload,
                headers=headers
            ) as response:
                # 流式转发响应
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        yield event_manager.create_direct_event("token", content=chunk)
        
    except Exception as e:
        yield event_manager.create_direct_event("error", error=f"处理power_knowledge时发生错误: {str(e)}")


async def _handle_power_knowledge(
    input_text: str,
    request_id: str,
    created_time: int,
    model: str
) -> Optional[str]:
    """处理power_knowledge指令（非流式版本，保持兼容性）"""
    try:
        chat_id = get_chat_id()
        headers = {"Authorization": MAXKB_APP_HEARDER}
        payload = {"message": input_text.replace('[power_knowledge]', '').strip()}
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                MAXKB_APP_CHAT + chat_id,
                json=payload,
                headers=headers
            ) as response:
                # 收集所有响应内容
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
        
        return buffer if buffer else None
    except Exception as e:
        return f"处理power_knowledge时发生错误: {str(e)}"


async def _handle_query_data(input_text: str) -> str:
    """处理query_data指令"""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: sqlsearch(input_text.replace('[query_data]', ''))
        )
        return (AGENT_PROMPT_V3 + 
                f"你是银供智能小助手，你的特长是快速思考。以下是数据库查询信息：{result}\n\n"
                f"上述信息可能有用也可能没用\n\n参考上述信息回答用户问题，以下是用户问题：{input_text.replace('[query_data]', '')} /no_thinking")
    except Exception as e:
        return f"处理query_data时发生错误: {str(e)}"


async def _handle_generate_report(input_text: str) -> str:
    """处理generate_report指令"""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            plotly_executor,
            lambda: generate_report(input_text.replace('[generate_report]', ''))
        )
        return (f"你是银供智能小助手，以下是数据库数据和报告链接：{result}\n\n"
                f"上述信息可能有用也可能没用\n\n参考上述信息分析数据输出报告链接回答用户问题，"
                f"以下是用户问题：{input_text.replace('[generate_report]', '')}")
    except Exception as e:
        return f"处理generate_report时发生错误: {str(e)}"


@router.get("/status")
async def get_service_status():
    """获取服务状态"""
    active_streams = streaming_service.get_active_streams()
    available_executors = agent_service.get_available_executors()
    
    return {
        "status": "healthy",
        "active_streams": len(active_streams),
        "available_executors": available_executors,
        "heartbeat_config": {
            "interval": heartbeat_config.interval,
            "timeout_threshold": heartbeat_config.timeout_threshold,
            "progress_interval": heartbeat_config.progress_interval
        }
    }


class HeartbeatConfigRequest(BaseModel):
    """心跳配置请求模型"""
    interval: float = Field(15.0, description="心跳间隔（秒）", ge=1.0, le=300.0)
    timeout_threshold: int = Field(300, description="超时阈值（次数）", ge=10, le=3600)
    progress_interval: float = Field(30.0, description="进度提示间隔（秒）", ge=5.0, le=600.0)


@router.post("/config/heartbeat")
async def update_heartbeat_config(config_request: HeartbeatConfigRequest):
    """更新心跳配置"""
    global heartbeat_config
    heartbeat_config = HeartbeatConfig(
        interval=config_request.interval,
        timeout_threshold=config_request.timeout_threshold,
        progress_interval=config_request.progress_interval
    )
    streaming_service.update_heartbeat_config(heartbeat_config)
    
    return {
        "message": "心跳配置已更新",
        "config": {
            "interval": config_request.interval,
            "timeout_threshold": config_request.timeout_threshold,
            "progress_interval": config_request.progress_interval
        }
    }


# ========== 可选：方便独立运行调试 ==========
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(
        title="重构后的智能体API",
        description="使用模块化设计的智能体服务",
        version="2.0.0"
    )

    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8000)