# -*- coding: utf-8 -*-
"""
回调处理器模块 - 提供智能体执行过程中的事件回调处理
"""
import asyncio
from typing import Any, Dict, Optional
from langchain.callbacks.base import AsyncCallbackHandler

from logger import logger


class StreamingCallbackHandler(AsyncCallbackHandler):
    """
    优化的流式回调处理器
    
    负责将智能体执行过程中的各种事件转换为标准化的事件格式，
    并通过队列传递给流式响应管理器
    """

    def __init__(self, queue: asyncio.Queue):
        """
        初始化回调处理器
        
        Args:
            queue: 用于传递事件的异步队列
        """
        self.queue = queue
        self._current_tool = None
        self._tool_start_time = None

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        处理LLM生成的新token
        
        Args:
            token: 生成的文本token
            kwargs: 其他参数
        """
        if token:
            try:
                await self.queue.put({
                    "type": "token",
                    "choices": [{"index": 0, "delta": {"content": token}}],
                    "timestamp": asyncio.get_event_loop().time()
                })
            except Exception as e:
                logger.error(f"处理LLM token时发生错误: {str(e)}")

    async def on_agent_action(self, action, **kwargs):
        """
        当智能体选择工具时调用
        
        Args:
            action: 智能体选择的动作
            kwargs: 其他参数
        """
        # 记录工具信息，但不发送事件（由on_tool_start处理）
        self._current_tool = {
            "name": action.tool,
            "input": action.tool_input
        }
        logger.debug(f"智能体选择工具: {action.tool}")

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """
        当工具开始执行时调用
        
        Args:
            serialized: 序列化的工具信息
            input_str: 工具输入
            kwargs: 其他参数
        """
        tool_name = serialized.get("name", "unknown_tool")
        self._tool_start_time = asyncio.get_event_loop().time()
        
        try:
            await self.queue.put({
                "type": "tool_start",
                "content": {
                    "tool": tool_name,
                    "input": input_str
                },
                "timestamp": self._tool_start_time
            })
            logger.debug(f"工具开始执行: {tool_name}")
        except Exception as e:
            logger.error(f"处理工具开始事件时发生错误: {str(e)}")

    async def on_tool_end(self, output: str, **kwargs):
        """
        当工具结束执行时调用
        
        Args:
            output: 工具输出
            kwargs: 其他参数
        """
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - self._tool_start_time if self._tool_start_time else 0
        
        try:
            await self.queue.put({
                "type": "tool_end",
                "data": {
                    "output": output,
                    "execution_time": execution_time
                },
                "timestamp": end_time
            })
            logger.debug(f"工具执行完成，耗时: {execution_time:.2f}秒")
        except Exception as e:
            logger.error(f"处理工具结束事件时发生错误: {str(e)}")

    async def on_agent_finish(self, finish, **kwargs):
        """
        当智能体结束执行时调用
        
        Args:
            finish: 完成信息
            kwargs: 其他参数
        """
        try:
            await self.queue.put({
                "type": "agent_finish",
                "data": {
                    "output": finish.return_values.get("output"),
                    "return_values": finish.return_values
                },
                "timestamp": asyncio.get_event_loop().time()
            })
            logger.debug("智能体执行完成")
        except Exception as e:
            logger.error(f"处理智能体完成事件时发生错误: {str(e)}")

    async def on_llm_error(self, error: Exception, **kwargs):
        """
        当LLM发生错误时调用
        
        Args:
            error: 错误信息
            kwargs: 其他参数
        """
        try:
            await self.queue.put({
                "type": "error",
                "data": {
                    "error": str(error),
                    "error_type": "llm_error"
                },
                "timestamp": asyncio.get_event_loop().time()
            })
            logger.error(f"LLM执行错误: {str(error)}")
        except Exception as e:
            logger.error(f"处理LLM错误事件时发生错误: {str(e)}")

    async def on_tool_error(self, error: Exception, **kwargs):
        """
        当工具发生错误时调用
        
        Args:
            error: 错误信息
            kwargs: 其他参数
        """
        try:
            await self.queue.put({
                "type": "error",
                "data": {
                    "error": str(error),
                    "error_type": "tool_error",
                    "tool": self._current_tool.get("name") if self._current_tool else "unknown"
                },
                "timestamp": asyncio.get_event_loop().time()
            })
            logger.error(f"工具执行错误: {str(error)}")
        except Exception as e:
            logger.error(f"处理工具错误事件时发生错误: {str(e)}")

    async def on_chain_error(self, error: Exception, **kwargs):
        """
        当链执行发生错误时调用
        
        Args:
            error: 错误信息
            kwargs: 其他参数
        """
        try:
            await self.queue.put({
                "type": "error",
                "data": {
                    "error": str(error),
                    "error_type": "chain_error"
                },
                "timestamp": asyncio.get_event_loop().time()
            })
            logger.error(f"链执行错误: {str(error)}")
        except Exception as e:
            logger.error(f"处理链错误事件时发生错误: {str(e)}")


class EnhancedStreamingCallbackHandler(StreamingCallbackHandler):
    """
    增强版流式回调处理器
    
    提供更多的事件处理和统计功能
    """
    
    def __init__(self, queue: asyncio.Queue, enable_stats: bool = True):
        """
        初始化增强版回调处理器
        
        Args:
            queue: 用于传递事件的异步队列
            enable_stats: 是否启用统计功能
        """
        super().__init__(queue)
        self.enable_stats = enable_stats
        self.stats = {
            "tokens_generated": 0,
            "tools_executed": 0,
            "total_execution_time": 0,
            "errors_count": 0
        } if enable_stats else None
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """处理LLM生成的新token（带统计）"""
        await super().on_llm_new_token(token, **kwargs)
        if self.enable_stats and token:
            self.stats["tokens_generated"] += 1
    
    async def on_tool_end(self, output: str, **kwargs):
        """处理工具结束（带统计）"""
        await super().on_tool_end(output, **kwargs)
        if self.enable_stats:
            self.stats["tools_executed"] += 1
            if self._tool_start_time:
                execution_time = asyncio.get_event_loop().time() - self._tool_start_time
                self.stats["total_execution_time"] += execution_time
    
    async def on_llm_error(self, error: Exception, **kwargs):
        """处理LLM错误（带统计）"""
        await super().on_llm_error(error, **kwargs)
        if self.enable_stats:
            self.stats["errors_count"] += 1
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取执行统计信息
        
        Returns:
            统计信息字典或None
        """
        return self.stats.copy() if self.enable_stats else None