"""
数据模型定义模块

该模块包含了所有API请求和响应的数据模型定义，
提供类型安全和数据验证功能。

Author: AI Assistant
Date: 2024
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class OpenAIMessage(BaseModel):
    """OpenAI消息格式"""
    role: str = Field(..., description="消息角色：user, assistant, system")
    content: str = Field(..., description="消息内容")


class OpenAIRequest(BaseModel):
    """OpenAI兼容的请求格式"""
    model: str = Field(default="Qwen3-30B-A3B-FP8", description="使用的模型名称")
    messages: List[OpenAIMessage] = Field(..., description="对话消息列表")
    stream: bool = Field(default=False, description="是否使用流式响应")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=15000, gt=0, description="最大生成token数")
    max_iterations: int = Field(default=5, gt=0, description="最大迭代次数")
    
    # 会话隔离字段
    conversation_id: Optional[str] = Field(None, description="会话ID，用于区分不同对话界面")
    user: Optional[str] = Field(None, description="用户ID，用于多用户场景")
    user_id: Optional[str] = Field(None, description="用户ID，用于多用户场景")
    session_id: Optional[str] = Field(None, description="会话ID，可以替代conversation_id使用")


class TrainData(BaseModel):
    """SQL训练数据模型"""
    question: Optional[str] = Field(None, description="问题描述")
    ddl: Optional[str] = Field(None, description="数据库DDL语句")
    documentation: Optional[str] = Field(None, description="文档说明")
    sql: Optional[str] = Field(None, description="SQL查询语句")
    app_id: Optional[str] = Field(None, description="应用ID")



class ToolStep(BaseModel):
    """工具执行步骤"""
    action: str = Field(..., description="执行的动作")
    input: dict = Field(..., description="输入参数")
    output: str = Field(..., description="输出结果")


class AgentResponse(BaseModel):
    """智能体响应模型"""
    input: str = Field(..., description="输入内容")
    output: str = Field(..., description="输出结果")
    steps: List[ToolStep] = Field(..., description="执行步骤列表")
    execution_time: float = Field(..., description="执行时间（秒）")


class ConversationClearRequest(BaseModel):
    """清空会话请求模型"""
    conversation_id: Optional[str] = Field(None, description="会话ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")


class ConversationHistoryResponse(BaseModel):
    """会话历史响应模型"""
    code: int = Field(..., description="响应状态码")
    data: dict = Field(..., description="响应数据")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    code: Optional[int] = Field(None, description="错误代码")


class SuccessResponse(BaseModel):
    """成功响应模型"""
    code: int = Field(default=200, description="响应状态码")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")