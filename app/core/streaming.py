# -*- coding: utf-8 -*-
"""
流式响应管理模块 - 提供流式响应和心跳机制的核心功能
"""
import asyncio
import time
from typing import Optional, AsyncGenerator, Callable, Any
from dataclasses import dataclass

from .events import EventGenerator


@dataclass
class HeartbeatConfig:
    """心跳配置"""
    interval: float = 15.0  # 心跳间隔（秒）
    timeout_threshold: int = 300  # 超时阈值（次数）
    progress_interval: float = 30.0  # 进度提示间隔（秒）


class HeartbeatManager:
    """心跳管理器 - 负责维护连接活跃状态"""
    
    def __init__(self, config: Optional[HeartbeatConfig] = None):
        """
        初始化心跳管理器
        
        Args:
            config: 心跳配置，如果为None则使用默认配置
        """
        self.config = config or HeartbeatConfig()
        self.last_heartbeat_time = time.time()
        self.last_progress_time = time.time()
        self.timeout_count = 0
        self.is_active = True
    
    def should_send_heartbeat(self) -> bool:
        """
        检查是否应该发送心跳
        
        Returns:
            是否需要发送心跳
        """
        current_time = time.time()
        return current_time - self.last_heartbeat_time > self.config.interval
    
    def should_send_progress(self) -> bool:
        """
        检查是否应该发送进度提示
        
        Returns:
            是否需要发送进度提示
        """
        current_time = time.time()
        return current_time - self.last_progress_time > self.config.progress_interval
    
    def reset_heartbeat(self):
        """重置心跳时间"""
        self.last_heartbeat_time = time.time()
        self.timeout_count = 0
    
    def reset_progress(self):
        """重置进度时间"""
        self.last_progress_time = time.time()
    
    def increment_timeout(self) -> bool:
        """
        增加超时计数
        
        Returns:
            是否超过超时阈值
        """
        self.timeout_count += 1
        return self.timeout_count > self.config.timeout_threshold
    
    def reset_timeout(self):
        """重置超时计数"""
        self.timeout_count = 0


class StreamingResponseManager:
    """流式响应管理器 - 统一管理流式响应的生成和发送"""
    
    def __init__(self, request_id: str, model: str, heartbeat_config: Optional[HeartbeatConfig] = None):
        """
        初始化流式响应管理器
        
        Args:
            request_id: 请求唯一标识
            model: 模型名称
            heartbeat_config: 心跳配置
        """
        self.event_generator = EventGenerator(request_id, model)
        self.heartbeat_manager = HeartbeatManager(heartbeat_config)
        self.final_output = ""
    
    async def generate_stream_response(
        self,
        task: asyncio.Task,
        queue: asyncio.Queue,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, str], None]] = None,
        on_tool_end: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> AsyncGenerator[str, None]:
        """
        生成流式响应
        
        Args:
            task: 异步任务
            queue: 事件队列
            on_token: token处理回调
            on_tool_start: 工具开始回调
            on_tool_end: 工具结束回调
            on_error: 错误处理回调
            
        Yields:
            格式化的SSE事件字符串
        """
        # 发送初始事件
        yield self.event_generator.generate_initial_event()
        
        try:
            while True:
                # 检查任务状态
                if task.done():
                    if queue.empty():
                        break
                    # 快速处理剩余事件
                    try:
                        event = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        await asyncio.sleep(0.1)
                        if self.heartbeat_manager.increment_timeout():
                            break
                        continue
                else:
                    # 任务未完成，非阻塞获取事件
                    try:
                        event = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        # 处理心跳和进度提示
                        await self._handle_idle_state()
                        await asyncio.sleep(0.1)
                        if self.heartbeat_manager.increment_timeout():
                            yield self.event_generator.generate_progress_event("正在处理中，请稍候...")
                            self.heartbeat_manager.reset_timeout()
                        continue
                
                # 重置超时计数
                self.heartbeat_manager.reset_timeout()
                
                # 处理事件
                event_output = await self._process_event(event, on_token, on_tool_start, on_tool_end)
                if event_output:
                    yield event_output
                
                # 检查是否结束
                if event.get("type") == "agent_finish":
                    break
            
            # 确保任务完成
            try:
                await asyncio.wait_for(task, timeout=0.5)
            except asyncio.TimeoutError:
                pass
            
            # 发送结束事件
            yield self.event_generator.generate_finish_event()
            yield self.event_generator.generate_done_event()
            
        except Exception as e:
            if on_error:
                on_error(e)
            yield self.event_generator.generate_error_event(str(e))
            yield self.event_generator.generate_done_event()
    
    async def _handle_idle_state(self):
        """处理空闲状态下的心跳和进度"""
        # 发送心跳
        if self.heartbeat_manager.should_send_heartbeat():
            self.heartbeat_manager.reset_heartbeat()
        
        # 发送进度提示
        if self.heartbeat_manager.should_send_progress():
            self.heartbeat_manager.reset_progress()
    
    async def _process_event(
        self,
        event: dict,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, str], None]] = None,
        on_tool_end: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        处理单个事件
        
        Args:
            event: 事件数据
            on_token: token处理回调
            on_tool_start: 工具开始回调
            on_tool_end: 工具结束回调
            
        Returns:
            格式化的SSE事件字符串或None
        """
        event_type = event.get("type")
        
        if event_type == "token":
            content = event["choices"][0]["delta"]["content"]
            self.final_output += content
            if on_token:
                on_token(content)
            return self.event_generator.generate_token_event(content)
        
        elif event_type == "tool_start":
            tool_name = event["content"]["tool"]
            tool_input = event["content"]["input"]
            if on_tool_start:
                on_tool_start(tool_name, tool_input)
            return self.event_generator.generate_tool_event(tool_name, tool_input, is_start=True)
        
        elif event_type == "tool_end":
            tool_output = event["data"]["output"]
            if on_tool_end:
                on_tool_end(tool_output)
            # 工具结束通常不需要发送事件，只记录
            return None
        
        elif event_type == "agent_finish":
            # 智能体完成，准备结束
            return None
        
        return None