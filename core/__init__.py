"""
核心模块包

该包包含了重构后的智能体服务核心组件，包括：
- 数据模型定义
- 会话管理
- 数据处理
- 流式响应处理

Author: AI Assistant
Date: 2024
"""

from .models import (
    OpenAIMessage,
    OpenAIRequest,
    TrainData,
    ToolStep,
    AgentResponse,
    ConversationClearRequest,
    ConversationHistoryResponse,
    ErrorResponse,
    SuccessResponse
)

from .conversation_manager import conversation_manager
from .data_processor import data_processor
from .streaming_handler import (
    StreamingCallbackHandler,
    StreamingResponseGenerator,
    HeartbeatManager
)

__all__ = [
    # 数据模型
    "OpenAIMessage",
    "OpenAIRequest", 
    "TrainData",
    "ToolStep",
    "AgentResponse",
    "ConversationClearRequest",
    "ConversationHistoryResponse",
    "ErrorResponse",
    "SuccessResponse",
    
    # 管理器和处理器
    "conversation_manager",
    "data_processor",
    
    # 流式处理组件
    "StreamingCallbackHandler",
    "StreamingResponseGenerator",
    "HeartbeatManager"
]