# -*- coding: utf-8 -*-
"""
辅助工具函数模块 - 提供常用的工具函数
"""
import time
import uuid
from typing import List, Optional, Dict, Any


def generate_request_id(prefix: str = "chatcmpl") -> str:
    """
    生成请求ID
    
    Args:
        prefix: ID前缀
        
    Returns:
        唯一的请求ID
    """
    timestamp = int(time.time())
    return f"{prefix}-{timestamp}"


def generate_unique_id() -> str:
    """
    生成唯一ID
    
    Returns:
        UUID字符串
    """
    return str(uuid.uuid4())


def extract_user_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    提取用户消息
    
    Args:
        messages: 消息列表
        
    Returns:
        用户消息列表
    """
    return [msg for msg in messages if msg.get("role") == "user"]


def get_last_user_message(messages: List[Dict[str, Any]]) -> Optional[str]:
    """
    获取最后一条用户消息内容
    
    Args:
        messages: 消息列表
        
    Returns:
        最后一条用户消息内容或None
    """
    user_messages = extract_user_messages(messages)
    if user_messages:
        return user_messages[-1].get("content")
    return None


def estimate_token_count(text: str) -> int:
    """
    估算文本的token数量（简化版本）
    
    Args:
        text: 输入文本
        
    Returns:
        估算的token数量
    """
    # 简化的token估算：平均每个字符约0.25个token
    return max(1, int(len(text) * 0.25))


def format_execution_time(seconds: float) -> str:
    """
    格式化执行时间
    
    Args:
        seconds: 执行时间（秒）
        
    Returns:
        格式化的时间字符串
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m{remaining_seconds:.1f}s"


def safe_get_nested_value(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """
    安全地获取嵌套字典的值
    
    Args:
        data: 数据字典
        keys: 键路径列表
        default: 默认值
        
    Returns:
        获取到的值或默认值
    """
    current = data
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError, IndexError):
        return default


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并多个字典
    
    Args:
        *dicts: 要合并的字典
        
    Returns:
        合并后的字典
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    将列表分块
    
    Args:
        lst: 输入列表
        chunk_size: 块大小
        
    Returns:
        分块后的列表
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    import re
    # 移除或替换不安全字符
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除连续的下划线
    sanitized = re.sub(r'_+', '_', sanitized)
    # 移除首尾的下划线和空格
    sanitized = sanitized.strip('_ ')
    return sanitized or "unnamed"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def is_valid_url(url: str) -> bool:
    """
    验证URL是否有效
    
    Args:
        url: URL字符串
        
    Returns:
        是否为有效URL
    """
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def get_client_ip(request) -> str:
    """
    获取客户端IP地址
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        客户端IP地址
    """
    # 检查代理头
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 返回直接连接的IP
    return request.client.host if request.client else "unknown"