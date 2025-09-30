# -*- coding: utf-8 -*-
"""
事件管理模块 - 定义和管理流式响应中的各种事件类型
"""
import json
import time
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, AsyncGenerator, Callable
from dataclasses import dataclass


class EventType(Enum):
    """事件类型枚举"""
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    AGENT_FINISH = "agent_finish"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    PROGRESS = "progress"


@dataclass
class StreamEvent:
    """流式事件数据类"""
    event_type: EventType
    content: Any
    metadata: Optional[Dict[str, Any]] = None


class CallbackBasedEventGenerator:
    """
    基于回调的事件生成器 - 统一事件处理机制
    
    将回调事件转换为OpenAI兼容的SSE格式，与StreamingCallbackHandler保持一致
    """
    
    def __init__(self, request_id: str, model: str, queue: Optional[asyncio.Queue] = None):
        """
        初始化事件生成器
        
        Args:
            request_id: 请求唯一标识
            model: 模型名称
            queue: 可选的事件队列，用于接收回调事件
        """
        self.request_id = request_id
        self.model = model
        self.created_time = int(time.time())
        self.queue = queue
        self._event_handlers = {
            "token": self._handle_token_event,
            "tool_start": self._handle_tool_start_event,
            "tool_end": self._handle_tool_end_event,
            "agent_finish": self._handle_agent_finish_event,
            "error": self._handle_error_event
        }
    
    async def process_callback_events(self) -> AsyncGenerator[str, None]:
        """
        处理来自回调队列的事件并生成SSE格式响应
        
        Yields:
            格式化的SSE事件字符串
        """
        if not self.queue:
            return
            
        # 发送初始事件
        yield self.generate_initial_event()
        
        try:
            while True:
                try:
                    # 等待队列中的事件，设置超时避免无限等待
                    event = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                    
                    # 处理事件
                    event_type = event.get("type")
                    if event_type in self._event_handlers:
                        sse_event = await self._event_handlers[event_type](event)
                        if sse_event:
                            yield sse_event
                    
                    # 标记任务完成
                    self.queue.task_done()
                    
                    # 如果是结束事件，发送完成标记
                    if event_type == "agent_finish":
                        yield self.generate_finish_event()
                        yield self.generate_done_event()
                        break
                        
                except asyncio.TimeoutError:
                    # 发送心跳事件保持连接
                    yield self.generate_heartbeat_event()
                    continue
                    
        except Exception as e:
            yield self.generate_error_event(f"事件处理错误: {str(e)}")
            yield self.generate_done_event()
    
    async def _handle_token_event(self, event: Dict[str, Any]) -> str:
        """处理token事件"""
        choices = event.get("choices", [])
        if choices and "delta" in choices[0] and "content" in choices[0]["delta"]:
            content = choices[0]["delta"]["content"]
            return self.generate_token_event(content)
        return ""
    
    async def _handle_tool_start_event(self, event: Dict[str, Any]) -> str:
        """处理工具开始事件"""
        content = event.get("content", {})
        tool_name = content.get("tool", "unknown_tool")
        tool_input = content.get("input", "")
        return self.generate_tool_event(tool_name, tool_input, is_start=True)
    
    async def _handle_tool_end_event(self, event: Dict[str, Any]) -> str:
        """处理工具结束事件"""
        data = event.get("data", {})
        # 可以根据需要添加工具输出的处理
        return self.generate_progress_event("工具执行完成")
    
    async def _handle_agent_finish_event(self, event: Dict[str, Any]) -> str:
        """处理智能体完成事件"""
        data = event.get("data", {})
        output = data.get("output", "")
        if output:
            return self.generate_token_event(output)
        return ""
    
    async def _handle_error_event(self, event: Dict[str, Any]) -> str:
        """处理错误事件"""
        data = event.get("data", {})
        error_msg = data.get("error", "未知错误")
        return self.generate_error_event(error_msg)

class EventGenerator(CallbackBasedEventGenerator):
    """
    传统事件生成器 - 保持向后兼容性
    
    继承CallbackBasedEventGenerator，提供原有的直接调用接口
    """
    
    def __init__(self, request_id: str, model: str):
        """
        初始化传统事件生成器
        
        Args:
            request_id: 请求唯一标识
            model: 模型名称
        """
        super().__init__(request_id, model, queue=None)
    
    def generate_initial_event(self) -> str:
        """
        生成初始事件（设置assistant角色）
        
        Returns:
            格式化的SSE事件字符串
        """
        initial_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(initial_data)}\n\n"
    
    def generate_token_event(self, content: str) -> str:
        """
        生成token事件
        
        Args:
            content: token内容
            
        Returns:
            格式化的SSE事件字符串
        """
        token_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(token_data)}\n\n"
    
    def generate_tool_event(self, tool_name: str, tool_input: str, is_start: bool = True) -> str:
        """
        生成工具事件
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            is_start: 是否为开始事件
            
        Returns:
            格式化的SSE事件字符串
        """
        status = "执行中" if is_start else "完成"
        content = f"\n\n[系统: 工具{tool_name}{status}，请稍后...]\n\n"
        
        status_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(status_data)}\n\n"
    
    def generate_heartbeat_event(self, content: str = "") -> str:
        """
        生成心跳事件
        
        Args:
            content: 心跳内容，默认为空
            
        Returns:
            格式化的SSE事件字符串
        """
        heartbeat_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(heartbeat_data)}\n\n"
    
    def generate_progress_event(self, message: str) -> str:
        """
        生成进度提示事件
        
        Args:
            message: 进度消息
            
        Returns:
            格式化的SSE事件字符串
        """
        progress_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n\n[系统提示: {message}]\n\n"},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(progress_data)}\n\n"
    
    def generate_error_event(self, error_message: str) -> str:
        """
        生成错误事件
        
        Args:
            error_message: 错误消息
            
        Returns:
            格式化的SSE事件字符串
        """
        error_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"[系统错误: {error_message}]"},
                "finish_reason": "error"
            }]
        }
        return f"data: {json.dumps(error_data)}\n\n"
    
    def generate_finish_event(self) -> str:
        """
        生成结束事件
        
        Returns:
            格式化的SSE事件字符串
        """
        finish_data = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        return f"data: {json.dumps(finish_data)}\n\n"
    
    def generate_done_event(self) -> str:
        """
        生成完成标记事件
        
        Returns:
            SSE完成标记
        """
        return "data: [DONE]\n\n"


class UnifiedEventManager:
    """
    统一事件管理器 - 整合回调和直接事件处理
    
    提供统一的接口来处理基于回调的事件和直接调用的事件
    """
    
    def __init__(self, request_id: str, model: str):
        """
        初始化统一事件管理器
        
        Args:
            request_id: 请求唯一标识
            model: 模型名称
        """
        self.request_id = request_id
        self.model = model
        self.queue = asyncio.Queue()
        self.callback_generator = CallbackBasedEventGenerator(request_id, model, self.queue)
        self.direct_generator = EventGenerator(request_id, model)
    
    async def create_callback_stream(self) -> AsyncGenerator[str, None]:
        """
        创建基于回调的流式响应
        
        Yields:
            格式化的SSE事件字符串
        """
        async for event in self.callback_generator.process_callback_events():
            yield event
    
    def create_direct_event(self, event_type: str, **kwargs) -> str:
        """
        创建直接事件
        
        Args:
            event_type: 事件类型
            **kwargs: 事件参数
            
        Returns:
            格式化的SSE事件字符串
        """
        if event_type == "initial":
            return self.direct_generator.generate_initial_event()
        elif event_type == "token":
            return self.direct_generator.generate_token_event(kwargs.get("content", ""))
        elif event_type == "tool":
            return self.direct_generator.generate_tool_event(
                kwargs.get("tool_name", ""),
                kwargs.get("tool_input", ""),
                kwargs.get("is_start", True)
            )
        elif event_type == "heartbeat":
            return self.direct_generator.generate_heartbeat_event(kwargs.get("content", ""))
        elif event_type == "progress":
            return self.direct_generator.generate_progress_event(kwargs.get("message", ""))
        elif event_type == "error":
            return self.direct_generator.generate_error_event(kwargs.get("error_message", ""))
        elif event_type == "finish":
            return self.direct_generator.generate_finish_event()
        elif event_type == "done":
            return self.direct_generator.generate_done_event()
        else:
            return ""
    
    async def put_callback_event(self, event: Dict[str, Any]):
        """
        向回调队列添加事件
        
        Args:
            event: 事件数据
        """
        await self.queue.put(event)
    
    def get_callback_queue(self) -> asyncio.Queue:
        """
        获取回调事件队列
        
        Returns:
            事件队列
        """
        return self.queue