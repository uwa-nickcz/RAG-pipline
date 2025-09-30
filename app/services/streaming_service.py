# -*- coding: utf-8 -*-
"""
流式服务模块 - 提供统一的流式响应处理服务
"""
import asyncio
import json
import time
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi.responses import StreamingResponse

from app.core.streaming import StreamingResponseManager, HeartbeatConfig
from app.core.callbacks import StreamingCallbackHandler, EnhancedStreamingCallbackHandler
from .agent_service import AgentService
from logger import logger


class StreamingService:
    """流式服务 - 统一管理流式响应处理"""
    
    def __init__(self, heartbeat_config: Optional[HeartbeatConfig] = None):
        """
        初始化流式服务
        
        Args:
            heartbeat_config: 心跳配置
        """
        self.agent_service = AgentService()
        self.heartbeat_config = heartbeat_config or HeartbeatConfig()
    
    async def create_agent_stream_response(
        self,
        input_text: str,
        model: str,
        executor_type: str = "metahuman",
        max_iterations: int = 5,
        enable_enhanced_callback: bool = False
    ) -> StreamingResponse:
        """
        创建智能体流式响应
        
        Args:
            input_text: 输入文本
            model: 模型名称
            executor_type: 执行器类型
            max_iterations: 最大迭代次数
            enable_enhanced_callback: 是否启用增强回调
            
        Returns:
            流式响应对象
        """
        # 生成请求ID
        request_id = f"chatcmpl-{int(time.time())}"
        
        # 创建事件队列和回调处理器
        queue = asyncio.Queue()
        
        if enable_enhanced_callback:
            callback = EnhancedStreamingCallbackHandler(queue, enable_stats=True)
        else:
            callback = StreamingCallbackHandler(queue)
        
        # 创建流式响应管理器
        stream_manager = StreamingResponseManager(
            request_id=request_id,
            model=model,
            heartbeat_config=self.heartbeat_config
        )
        
        async def event_generator() -> AsyncGenerator[str, None]:
            """事件生成器"""
            try:
                # 启动智能体任务
                task = await self.agent_service.execute_agent_streaming(
                    input_text=input_text,
                    queue=queue,
                    executor_type=executor_type,
                    max_iterations=max_iterations,
                    callbacks=[callback]
                )
                
                # 生成流式响应
                async for event in stream_manager.generate_stream_response(
                    task=task,
                    queue=queue,
                    on_token=self._on_token_received,
                    on_tool_start=self._on_tool_start,
                    on_tool_end=self._on_tool_end,
                    on_error=self._on_error
                ):
                    yield event
                
                # 记录统计信息（如果启用）
                if enable_enhanced_callback and hasattr(callback, 'get_stats'):
                    stats = callback.get_stats()
                    if stats:
                        logger.info(f"执行统计: {stats}")
                        
            except Exception as e:
                logger.error(f"流式响应生成失败: {str(e)}")
                # 发送错误事件
                yield stream_manager.event_generator.generate_error_event(str(e))
                yield stream_manager.event_generator.generate_done_event()
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    async def create_error_stream_response(
        self,
        error_message: str,
        model: str
    ) -> StreamingResponse:
        """
        创建错误流式响应
        
        Args:
            error_message: 错误消息
            model: 模型名称
            
        Returns:
            错误流式响应
        """
        request_id = f"error-{int(time.time())}"
        
        async def error_generator():
            """错误事件生成器"""
            error_data = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": error_message},
                    "finish_reason": "error"
                }]
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream"
        )
    
    def _on_token_received(self, token: str):
        """token接收回调"""
        logger.debug(f"接收到token: {token[:50]}...")
    
    def _on_tool_start(self, tool_name: str, tool_input: str):
        """工具开始回调"""
        logger.info(f"工具开始执行: {tool_name}")
    
    def _on_tool_end(self, tool_output: str):
        """工具结束回调"""
        logger.info(f"工具执行完成，输出长度: {len(tool_output)}")
    
    def _on_error(self, error: Exception):
        """错误处理回调"""
        logger.error(f"流式处理错误: {str(error)}")
    
    def update_heartbeat_config(self, config: HeartbeatConfig):
        """
        更新心跳配置
        
        Args:
            config: 新的心跳配置
        """
        self.heartbeat_config = config
        logger.info(f"心跳配置已更新: 间隔={config.interval}s, 超时阈值={config.timeout_threshold}")


class AdvancedStreamingService(StreamingService):
    """高级流式服务 - 提供更多功能"""
    
    def __init__(self, heartbeat_config: Optional[HeartbeatConfig] = None):
        """初始化高级流式服务"""
        super().__init__(heartbeat_config)
        self.active_streams: Dict[str, Dict[str, Any]] = {}
    
    async def create_monitored_stream_response(
        self,
        input_text: str,
        model: str,
        executor_type: str = "metahuman",
        max_iterations: int = 5,
        stream_id: Optional[str] = None
    ) -> StreamingResponse:
        """
        创建可监控的流式响应
        
        Args:
            input_text: 输入文本
            model: 模型名称
            executor_type: 执行器类型
            max_iterations: 最大迭代次数
            stream_id: 流ID，用于监控
            
        Returns:
            可监控的流式响应
        """
        if not stream_id:
            stream_id = f"stream-{int(time.time())}"
        
        # 记录活跃流
        self.active_streams[stream_id] = {
            "start_time": time.time(),
            "input_text": input_text,
            "model": model,
            "executor_type": executor_type,
            "status": "active"
        }
        
        try:
            response = await self.create_agent_stream_response(
                input_text=input_text,
                model=model,
                executor_type=executor_type,
                max_iterations=max_iterations,
                enable_enhanced_callback=True
            )
            
            # 更新状态
            self.active_streams[stream_id]["status"] = "completed"
            self.active_streams[stream_id]["end_time"] = time.time()
            
            return response
            
        except Exception as e:
            # 更新错误状态
            self.active_streams[stream_id]["status"] = "error"
            self.active_streams[stream_id]["error"] = str(e)
            self.active_streams[stream_id]["end_time"] = time.time()
            raise
    
    def get_stream_status(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """
        获取流状态
        
        Args:
            stream_id: 流ID
            
        Returns:
            流状态信息或None
        """
        return self.active_streams.get(stream_id)
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有活跃流
        
        Returns:
            活跃流字典
        """
        return {k: v for k, v in self.active_streams.items() if v["status"] == "active"}
    
    def cleanup_completed_streams(self, max_age_seconds: int = 3600):
        """
        清理已完成的流记录
        
        Args:
            max_age_seconds: 最大保留时间（秒）
        """
        current_time = time.time()
        to_remove = []
        
        for stream_id, stream_info in self.active_streams.items():
            if stream_info["status"] != "active":
                end_time = stream_info.get("end_time", stream_info["start_time"])
                if current_time - end_time > max_age_seconds:
                    to_remove.append(stream_id)
        
        for stream_id in to_remove:
            del self.active_streams[stream_id]
        
        if to_remove:
            logger.info(f"清理了 {len(to_remove)} 个已完成的流记录")