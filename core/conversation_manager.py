"""
会话管理模块

该模块负责管理多轮对话的会话状态，包括会话存储、历史记录管理、
会话隔离等功能。支持基于conversation_id、user_id、session_id的会话隔离。

Author: AI Assistant
Date: 2024
"""

import asyncio
from typing import Dict, List, Optional
from .models import OpenAIMessage, OpenAIRequest


class ConversationManager:
    """会话管理器
    
    负责管理多个会话的状态和历史记录，提供线程安全的会话操作。
    在生产环境中建议使用Redis或数据库替代内存存储。
    """
    
    def __init__(self):
        """初始化会话管理器"""
        self._conversation_history: Dict[str, List[OpenAIMessage]] = {}
        self._lock = asyncio.Lock()
    
    async def get_conversation_key(self, request: OpenAIRequest) -> str:
        """生成会话唯一标识符
        
        Args:
            request: OpenAI请求对象
            
        Returns:
            str: 会话唯一标识符
        """
        if request.user:
            return f"conv_{request.user}"
        elif request.session_id:
            return f"session_{request.session_id}"
        elif request.user_id:
            return f"user_{request.user_id}_default"
        else:
            # 如果没有提供任何ID，使用默认会话
            return "default_conversation"
    
    async def get_conversation_history(self, conversation_key: str) -> List[OpenAIMessage]:
        """获取会话历史
        
        Args:
            conversation_key: 会话标识符
            
        Returns:
            List[OpenAIMessage]: 会话历史消息列表
        """
        async with self._lock:
            return self._conversation_history.get(conversation_key, []).copy()
    
    async def update_conversation_history(self, conversation_key: str, messages: List[OpenAIMessage]) -> None:
        """更新会话历史（自动限制为最近三轮对话）
        
        Args:
            conversation_key: 会话标识符
            messages: 新的消息列表
        """
        async with self._lock:
            # 限制历史对话为最近三轮，防止内存无限增长
            limited_messages = self._limit_to_recent_turns(messages, max_turns=3)
            self._conversation_history[conversation_key] = [msg.copy() for msg in limited_messages]
    
    async def add_message_to_conversation(self, conversation_key: str, message: OpenAIMessage) -> None:
        """向会话添加单条消息（自动维护三轮对话限制）
        
        Args:
            conversation_key: 会话标识符
            message: 要添加的消息
        """
        async with self._lock:
            if conversation_key not in self._conversation_history:
                self._conversation_history[conversation_key] = []
            
            # 添加新消息
            self._conversation_history[conversation_key].append(message.copy())
            
            # 限制历史对话为最近三轮，防止内存无限增长
            self._conversation_history[conversation_key] = self._limit_to_recent_turns(
                self._conversation_history[conversation_key], max_turns=3
            )
    
    async def clear_conversation_history(self, conversation_key: str) -> None:
        """清空指定会话历史
        
        Args:
            conversation_key: 会话标识符
        """
        async with self._lock:
            if conversation_key in self._conversation_history:
                del self._conversation_history[conversation_key]
    
    async def merge_messages(self, request: OpenAIRequest) -> List[OpenAIMessage]:
        """合并请求消息和历史消息
        
        根据请求中的消息数量和历史记录，智能合并消息：
        - 如果请求中只有一条消息且有历史记录，则合并历史
        - 如果请求中有多条消息或无历史记录，则使用请求中的消息
        - 历史对话数据自动限制为最近三轮对话（6条消息：3个用户消息 + 3个助手消息）
        
        Args:
            request: OpenAI请求对象
            
        Returns:
            List[OpenAIMessage]: 合并后的消息列表
        """
        conversation_key = await self.get_conversation_key(request)
        stored_history = await self.get_conversation_history(conversation_key)
        
        # 历史记录已经在存储时自动限制为最近三轮对话
        
        if len(request.messages) == 1 and stored_history:
            # 单条消息 + 有历史记录：合并历史
            all_messages = stored_history + request.messages
        else:
            # 多条消息或无历史记录：使用请求中的消息
            all_messages = request.messages
        
        # 更新会话历史（自动限制为三轮对话）
        full_history = stored_history + request.messages if len(request.messages) == 1 and stored_history else request.messages
        await self.update_conversation_history(conversation_key, full_history)
        
        return all_messages
    
    async def save_assistant_response(self, conversation_key: str, response_content: str) -> None:
        """保存助手响应到会话历史
        
        Args:
            conversation_key: 会话标识符
            response_content: 助手响应内容
        """
        if response_content.strip():
            assistant_message = OpenAIMessage(role="assistant", content=response_content)
            await self.add_message_to_conversation(conversation_key, assistant_message)
    
    def get_conversation_stats(self) -> Dict[str, int]:
        """获取会话统计信息
        
        Returns:
            Dict[str, int]: 包含会话数量和总消息数的统计信息
        """
        total_conversations = len(self._conversation_history)
        total_messages = sum(len(messages) for messages in self._conversation_history.values())
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages
        }
    
    def _limit_to_recent_turns(self, messages: List[OpenAIMessage], max_turns: int = 3) -> List[OpenAIMessage]:
        """限制消息列表为最近的几轮对话
        
        Args:
            messages: 原始消息列表
            max_turns: 最大轮数（默认3轮）
            
        Returns:
            List[OpenAIMessage]: 限制后的消息列表
        """
        if not messages:
            return []
        
        # 计算需要保留的消息数量（每轮对话包含一个用户消息和一个助手消息）
        max_messages = max_turns * 2
        
        # 从后往前取最近的消息
        if len(messages) <= max_messages:
            return messages
        else:
            return messages[-max_messages:]


# 全局会话管理器实例
conversation_manager = ConversationManager()