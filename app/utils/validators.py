# -*- coding: utf-8 -*-
"""
验证器模块 - 提供数据验证功能
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError


def validate_openai_request(request_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证OpenAI请求格式
    
    Args:
        request_data: 请求数据
        
    Returns:
        (是否有效, 错误消息)
    """
    try:
        # 检查必需字段
        if "messages" not in request_data:
            return False, "缺少messages字段"
        
        messages = request_data["messages"]
        if not isinstance(messages, list) or len(messages) == 0:
            return False, "messages必须是非空列表"
        
        # 验证消息格式
        for i, message in enumerate(messages):
            if not isinstance(message, dict):
                return False, f"消息{i}必须是字典格式"
            
            if "role" not in message:
                return False, f"消息{i}缺少role字段"
            
            if "content" not in message:
                return False, f"消息{i}缺少content字段"
            
            if message["role"] not in ["user", "assistant", "system"]:
                return False, f"消息{i}的role字段值无效"
        
        # 检查是否有用户消息
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        if not user_messages:
            return False, "至少需要一条用户消息"
        
        return True, None
        
    except Exception as e:
        return False, f"验证过程中发生错误: {str(e)}"


def validate_executor_type(executor_type: str, available_types: List[str]) -> tuple[bool, Optional[str]]:
    """
    验证执行器类型
    
    Args:
        executor_type: 执行器类型
        available_types: 可用的执行器类型列表
        
    Returns:
        (是否有效, 错误消息)
    """
    if not executor_type:
        return False, "执行器类型不能为空"
    
    if executor_type not in available_types:
        return False, f"不支持的执行器类型: {executor_type}，可用类型: {', '.join(available_types)}"
    
    return True, None


def validate_max_iterations(max_iterations: int) -> tuple[bool, Optional[str]]:
    """
    验证最大迭代次数
    
    Args:
        max_iterations: 最大迭代次数
        
    Returns:
        (是否有效, 错误消息)
    """
    if max_iterations <= 0:
        return False, "最大迭代次数必须大于0"
    
    if max_iterations > 20:
        return False, "最大迭代次数不能超过20"
    
    return True, None


def validate_temperature(temperature: float) -> tuple[bool, Optional[str]]:
    """
    验证温度参数
    
    Args:
        temperature: 温度参数
        
    Returns:
        (是否有效, 错误消息)
    """
    if temperature < 0.0 or temperature > 2.0:
        return False, "温度参数必须在0.0到2.0之间"
    
    return True, None


def validate_max_tokens(max_tokens: int) -> tuple[bool, Optional[str]]:
    """
    验证最大token数
    
    Args:
        max_tokens: 最大token数
        
    Returns:
        (是否有效, 错误消息)
    """
    if max_tokens <= 0:
        return False, "最大token数必须大于0"
    
    if max_tokens > 32000:
        return False, "最大token数不能超过32000"
    
    return True, None


def validate_model_name(model_name: str, supported_models: Optional[List[str]] = None) -> tuple[bool, Optional[str]]:
    """
    验证模型名称
    
    Args:
        model_name: 模型名称
        supported_models: 支持的模型列表，如果为None则不检查
        
    Returns:
        (是否有效, 错误消息)
    """
    if not model_name or not model_name.strip():
        return False, "模型名称不能为空"
    
    if supported_models and model_name not in supported_models:
        return False, f"不支持的模型: {model_name}，支持的模型: {', '.join(supported_models)}"
    
    return True, None


def validate_heartbeat_config(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证心跳配置
    
    Args:
        config: 心跳配置字典
        
    Returns:
        (是否有效, 错误消息)
    """
    try:
        interval = config.get("interval", 15.0)
        timeout_threshold = config.get("timeout_threshold", 300)
        progress_interval = config.get("progress_interval", 30.0)
        
        if not isinstance(interval, (int, float)) or interval <= 0:
            return False, "心跳间隔必须是正数"
        
        if not isinstance(timeout_threshold, int) or timeout_threshold <= 0:
            return False, "超时阈值必须是正整数"
        
        if not isinstance(progress_interval, (int, float)) or progress_interval <= 0:
            return False, "进度间隔必须是正数"
        
        if interval >= progress_interval:
            return False, "心跳间隔应该小于进度间隔"
        
        return True, None
        
    except Exception as e:
        return False, f"验证心跳配置时发生错误: {str(e)}"


def validate_connection_id(connection_id: str) -> tuple[bool, Optional[str]]:
    """
    验证连接ID
    
    Args:
        connection_id: 连接ID
        
    Returns:
        (是否有效, 错误消息)
    """
    if not connection_id or not connection_id.strip():
        return False, "连接ID不能为空"
    
    if len(connection_id) > 100:
        return False, "连接ID长度不能超过100个字符"
    
    # 检查是否包含非法字符
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', connection_id):
        return False, "连接ID只能包含字母、数字、下划线和连字符"
    
    return True, None


def validate_stream_id(stream_id: str) -> tuple[bool, Optional[str]]:
    """
    验证流ID
    
    Args:
        stream_id: 流ID
        
    Returns:
        (是否有效, 错误消息)
    """
    return validate_connection_id(stream_id)  # 使用相同的验证规则


def validate_metadata(metadata: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证元数据
    
    Args:
        metadata: 元数据字典
        
    Returns:
        (是否有效, 错误消息)
    """
    if not isinstance(metadata, dict):
        return False, "元数据必须是字典格式"
    
    # 检查元数据大小
    import json
    try:
        metadata_str = json.dumps(metadata)
        if len(metadata_str) > 10000:  # 10KB限制
            return False, "元数据大小不能超过10KB"
    except (TypeError, ValueError):
        return False, "元数据包含不可序列化的内容"
    
    return True, None


class RequestValidator:
    """请求验证器类"""
    
    def __init__(self, supported_models: Optional[List[str]] = None):
        """
        初始化验证器
        
        Args:
            supported_models: 支持的模型列表
        """
        self.supported_models = supported_models or []
    
    def validate_complete_request(self, request_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        完整验证请求
        
        Args:
            request_data: 请求数据
            
        Returns:
            (是否有效, 错误消息)
        """
        # 验证OpenAI请求格式
        valid, error = validate_openai_request(request_data)
        if not valid:
            return False, error
        
        # 验证模型名称
        model = request_data.get("model", "")
        if self.supported_models:
            valid, error = validate_model_name(model, self.supported_models)
            if not valid:
                return False, error
        
        # 验证温度参数
        temperature = request_data.get("temperature", 0.5)
        valid, error = validate_temperature(temperature)
        if not valid:
            return False, error
        
        # 验证最大token数
        max_tokens = request_data.get("max_tokens", 15000)
        valid, error = validate_max_tokens(max_tokens)
        if not valid:
            return False, error
        
        # 验证最大迭代次数
        max_iterations = request_data.get("max_iterations", 5)
        valid, error = validate_max_iterations(max_iterations)
        if not valid:
            return False, error
        
        return True, None