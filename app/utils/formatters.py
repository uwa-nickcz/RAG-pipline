# -*- coding: utf-8 -*-
"""
格式化器模块 - 提供数据格式化功能
"""
import json
import time
from typing import Dict, Any, List, Optional
from .helpers import estimate_token_count, generate_request_id


def format_openai_response(
    content: str,
    model: str,
    request_id: Optional[str] = None,
    input_text: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
    execution_time: Optional[float] = None
) -> Dict[str, Any]:
    """
    格式化OpenAI兼容的响应
    
    Args:
        content: 响应内容
        model: 模型名称
        request_id: 请求ID
        input_text: 输入文本（用于计算token）
        steps: 执行步骤
        execution_time: 执行时间
        
    Returns:
        OpenAI兼容的响应字典
    """
    if not request_id:
        request_id = generate_request_id()
    
    created_timestamp = int(time.time())
    
    # 计算token数量
    input_tokens = estimate_token_count(input_text) if input_text else 0
    output_tokens = estimate_token_count(content)
    
    response = {
        "id": request_id,
        "object": "chat.completion",
        "created": created_timestamp,
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    }
    
    # 添加扩展信息
    if steps is not None or execution_time is not None:
        response["agent_details"] = {}
        if input_text:
            response["agent_details"]["input"] = input_text
        if steps:
            response["agent_details"]["steps"] = steps
        if execution_time:
            response["agent_details"]["execution_time"] = execution_time
    
    return response


def format_streaming_chunk(
    content: str,
    model: str,
    request_id: str,
    created_time: Optional[int] = None,
    finish_reason: Optional[str] = None,
    role: Optional[str] = None
) -> str:
    """
    格式化流式响应块
    
    Args:
        content: 内容
        model: 模型名称
        request_id: 请求ID
        created_time: 创建时间
        finish_reason: 结束原因
        role: 角色（仅在首次设置时使用）
        
    Returns:
        格式化的SSE事件字符串
    """
    if created_time is None:
        created_time = int(time.time())
    
    delta = {}
    if role:
        delta["role"] = role
    if content:
        delta["content"] = content
    
    chunk_data = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason
        }]
    }
    
    return f"data: {json.dumps(chunk_data)}\n\n"


def format_error_response(
    error_message: str,
    error_type: str = "server_error",
    error_code: int = 500,
    model: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    格式化错误响应
    
    Args:
        error_message: 错误消息
        error_type: 错误类型
        error_code: 错误代码
        model: 模型名称
        request_id: 请求ID
        
    Returns:
        错误响应字典
    """
    if not request_id:
        request_id = generate_request_id("error")
    
    return {
        "error": {
            "message": error_message,
            "type": error_type,
            "code": error_code
        },
        "id": request_id,
        "object": "error",
        "created": int(time.time()),
        "model": model or "unknown"
    }


def format_streaming_error(
    error_message: str,
    model: str,
    request_id: Optional[str] = None
) -> str:
    """
    格式化流式错误响应
    
    Args:
        error_message: 错误消息
        model: 模型名称
        request_id: 请求ID
        
    Returns:
        格式化的SSE错误事件字符串
    """
    if not request_id:
        request_id = generate_request_id("error")
    
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
    
    return f"data: {json.dumps(error_data)}\n\n"


def format_heartbeat_event(
    model: str,
    request_id: str,
    created_time: Optional[int] = None,
    content: str = ""
) -> str:
    """
    格式化心跳事件
    
    Args:
        model: 模型名称
        request_id: 请求ID
        created_time: 创建时间
        content: 心跳内容
        
    Returns:
        格式化的心跳事件字符串
    """
    if created_time is None:
        created_time = int(time.time())
    
    heartbeat_data = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": content},
            "finish_reason": None
        }]
    }
    
    return f"data: {json.dumps(heartbeat_data)}\n\n"


def format_progress_event(
    message: str,
    model: str,
    request_id: str,
    created_time: Optional[int] = None
) -> str:
    """
    格式化进度事件
    
    Args:
        message: 进度消息
        model: 模型名称
        request_id: 请求ID
        created_time: 创建时间
        
    Returns:
        格式化的进度事件字符串
    """
    if created_time is None:
        created_time = int(time.time())
    
    progress_content = f"\n\n[系统提示: {message}]\n\n"
    
    progress_data = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": progress_content},
            "finish_reason": None
        }]
    }
    
    return f"data: {json.dumps(progress_data)}\n\n"


def format_tool_event(
    tool_name: str,
    tool_input: str,
    model: str,
    request_id: str,
    is_start: bool = True,
    created_time: Optional[int] = None
) -> str:
    """
    格式化工具事件
    
    Args:
        tool_name: 工具名称
        tool_input: 工具输入
        model: 模型名称
        request_id: 请求ID
        is_start: 是否为开始事件
        created_time: 创建时间
        
    Returns:
        格式化的工具事件字符串
    """
    if created_time is None:
        created_time = int(time.time())
    
    status = "执行中" if is_start else "完成"
    tool_content = f"\n\n[系统: 工具{tool_name}{status}，请稍后...]\n\n"
    
    tool_data = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": tool_content},
            "finish_reason": None
        }]
    }
    
    return f"data: {json.dumps(tool_data)}\n\n"


def format_finish_event(
    model: str,
    request_id: str,
    created_time: Optional[int] = None
) -> str:
    """
    格式化结束事件
    
    Args:
        model: 模型名称
        request_id: 请求ID
        created_time: 创建时间
        
    Returns:
        格式化的结束事件字符串
    """
    if created_time is None:
        created_time = int(time.time())
    
    finish_data = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    
    return f"data: {json.dumps(finish_data)}\n\n"


def format_done_event() -> str:
    """
    格式化完成标记事件
    
    Returns:
        SSE完成标记
    """
    return "data: [DONE]\n\n"


def format_service_status(
    active_streams: int,
    available_executors: List[str],
    heartbeat_config: Dict[str, Any],
    additional_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    格式化服务状态响应
    
    Args:
        active_streams: 活跃流数量
        available_executors: 可用执行器列表
        heartbeat_config: 心跳配置
        additional_info: 额外信息
        
    Returns:
        服务状态字典
    """
    status = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "active_streams": active_streams,
        "available_executors": available_executors,
        "heartbeat_config": heartbeat_config
    }
    
    if additional_info:
        status.update(additional_info)
    
    return status


class ResponseFormatter:
    """响应格式化器类"""
    
    def __init__(self, default_model: str = "unknown"):
        """
        初始化格式化器
        
        Args:
            default_model: 默认模型名称
        """
        self.default_model = default_model
    
    def format_success_response(
        self,
        content: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        格式化成功响应
        
        Args:
            content: 响应内容
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            格式化的响应
        """
        return format_openai_response(
            content=content,
            model=model or self.default_model,
            **kwargs
        )
    
    def format_error(
        self,
        error_message: str,
        error_type: str = "server_error",
        error_code: int = 500,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        格式化错误响应
        
        Args:
            error_message: 错误消息
            error_type: 错误类型
            error_code: 错误代码
            model: 模型名称
            
        Returns:
            格式化的错误响应
        """
        return format_error_response(
            error_message=error_message,
            error_type=error_type,
            error_code=error_code,
            model=model or self.default_model
        )