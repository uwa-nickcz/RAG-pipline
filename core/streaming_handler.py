"""
流式响应处理模块

该模块负责处理流式响应的生成、心跳机制、事件处理等功能，
提供统一的流式输出接口和回调处理机制。

Author: AI Assistant
Date: 2024
"""

import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from langchain.callbacks.base import AsyncCallbackHandler
from fastapi.responses import StreamingResponse


class StreamingCallbackHandler(AsyncCallbackHandler):
    """流式输出回调处理器
    
    处理LLM生成过程中的各种事件，包括token生成、工具调用等。
    """

    def __init__(self, queue: asyncio.Queue):
        """初始化回调处理器
        
        Args:
            queue: 事件队列
        """
        self.queue = queue

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """处理LLM生成的新token
        
        Args:
            token: 新生成的token
        """
        if token:
            await self.queue.put({
                "type": "token",
                "choices": [{"index": 0, "delta": {"content": token}}]
            })

    async def on_agent_action(self, action, **kwargs):
        """当智能体选择工具时调用
        
        Args:
            action: 智能体动作
        """
        pass

    async def on_tool_start(self, serialized, input_str, **kwargs):
        """当工具开始执行时调用
        
        Args:
            serialized: 序列化的工具信息
            input_str: 输入字符串
        """
        tool_name = serialized.get("name", "unknown_tool")
        await self.queue.put({
            "type": "tool_start",
            "content": {
                "tool": tool_name,
                "input": input_str
            }
        })

    async def on_tool_end(self, output, **kwargs):
        """当工具结束执行时调用
        
        Args:
            output: 工具输出
        """
        await self.queue.put({
            "type": "tool_end",
            "data": {
                "output": output
            }
        })

    async def on_agent_finish(self, finish, **kwargs):
        """当智能体结束执行时调用
        
        Args:
            finish: 完成信息
        """
        await self.queue.put({
            "type": "agent_finish",
            "data": {
                "output": finish.return_values.get("output")
            }
        })


class StreamingResponseGenerator:
    """流式响应生成器
    
    负责生成符合OpenAI格式的流式响应，包括心跳机制和错误处理。
    """
    
    def __init__(self, model: str, heartbeat_interval: int = 30):
        """初始化流式响应生成器
        
        Args:
            model: 模型名称
            heartbeat_interval: 心跳间隔（秒）
        """
        self.model = model
        self.heartbeat_interval = heartbeat_interval
    
    def create_chunk_data(self, request_id: str, created_time: int, 
                         content: str = "", finish_reason: Optional[str] = None, 
                         role: Optional[str] = None) -> Dict[str, Any]:
        """创建流式响应数据块
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            content: 内容
            finish_reason: 结束原因
            role: 角色
            
        Returns:
            Dict[str, Any]: 响应数据块
        """
        delta = {}
        if role:
            delta["role"] = role
        if content:
            delta["content"] = content
        
        return {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason
            }]
        }
    
    def create_error_data(self, request_id: str, created_time: int, error_message: str) -> Dict[str, Any]:
        """创建错误响应数据
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            error_message: 错误消息
            
        Returns:
            Dict[str, Any]: 错误响应数据
        """
        return {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": error_message},
                "finish_reason": "error"
            }]
        }
    
    async def generate_error_response(self, error_message: str) -> AsyncGenerator[str, None]:
        """生成错误响应
        
        Args:
            error_message: 错误消息
            
        Yields:
            str: 流式响应数据
        """
        error_data = {
            "id": "error",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": error_message},
                "finish_reason": "error"
            }]
        }
        
        yield f"data: {json.dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
    
    async def generate_processing_hint(self, request_id: str, created_time: int, 
                                     hint_message: str = " ") -> str:
        """生成处理提示
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            hint_message: 提示消息
            
        Returns:
            str: 处理提示数据
        """
        processing_data = self.create_chunk_data(request_id, created_time, hint_message)
        return f"data: {json.dumps(processing_data)}\n\n"
    
    async def generate_heartbeat(self, request_id: str, created_time: int) -> str:
        """生成心跳数据
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            
        Returns:
            str: 心跳数据
        """
        heartbeat_data = self.create_chunk_data(request_id, created_time, "")
        return f"data: {json.dumps(heartbeat_data)}\n\n"
    
    async def generate_initial_response(self, request_id: str, created_time: int) -> str:
        """生成初始响应
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            
        Returns:
            str: 初始响应数据
        """
        initial_data = self.create_chunk_data(request_id, created_time, role="assistant")
        return f"data: {json.dumps(initial_data)}\n\n"
    
    async def generate_content_chunk(self, request_id: str, created_time: int, content: str) -> str:
        """生成内容块
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            content: 内容
            
        Returns:
            str: 内容块数据
        """
        token_data = self.create_chunk_data(request_id, created_time, content)
        return f"data: {json.dumps(token_data)}\n\n"
    
    async def generate_finish_response(self, request_id: str, created_time: int) -> str:
        """生成结束响应
        
        Args:
            request_id: 请求ID
            created_time: 创建时间
            
        Returns:
            str: 结束响应数据
        """
        finish_data = self.create_chunk_data(request_id, created_time, finish_reason="stop")
        return f"data: {json.dumps(finish_data)}\n\n" + "data: [DONE]\n\n"
    
    def create_streaming_response(self, generator: AsyncGenerator[str, None]) -> StreamingResponse:
        """创建流式响应对象
        
        Args:
            generator: 异步生成器
            
        Returns:
            StreamingResponse: FastAPI流式响应对象
        """
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )


class HeartbeatManager:
    """心跳管理器
    
    负责管理流式响应中的心跳机制，防止连接超时。
    """
    
    def __init__(self, interval: int = 30):
        """初始化心跳管理器
        
        Args:
            interval: 心跳间隔（秒）
        """
        self.interval = interval
        self.last_heartbeat_time = time.time()
    
    def should_send_heartbeat(self) -> bool:
        """检查是否应该发送心跳
        
        Returns:
            bool: 是否应该发送心跳
        """
        current_time = time.time()
        return current_time - self.last_heartbeat_time > self.interval
    
    def update_heartbeat_time(self) -> None:
        """更新心跳时间"""
        self.last_heartbeat_time = time.time()
    
    def reset(self) -> None:
        """重置心跳时间"""
        self.last_heartbeat_time = time.time()