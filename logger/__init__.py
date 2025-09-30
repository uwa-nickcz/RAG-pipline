# -*- coding: utf-8 -*-
"""
日志模块 - 提供统一的日志记录功能

提供彩色控制台输出和文件记录，支持不同日志级别和格式化。
同时提供异常处理装饰器，用于捕获和记录函数执行过程中的异常。
"""
import logging
import os
import functools
import traceback
from typing import Callable, Any, Optional
from pathlib import Path

# 日志颜色配置
COLORS = {
    'DEBUG': '\033[96m',    # 青色
    'INFO': '\033[92m',     # 绿色
    'WARNING': '\033[93m',  # 黄色
    'ERROR': '\033[91m',    # 红色
    'CRITICAL': '\033[1;91m',  # 粗体红色
    'RESET': '\033[0m'      # 重置颜色
}

# 日志级别映射
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器，为不同级别的日志添加颜色"""
    
    def format(self, record):
        levelname = record.levelname
        message = super().format(record)
        color = COLORS.get(levelname, COLORS['RESET'])
        return f"{color}{message}{COLORS['RESET']}"


def setup_logger(name: str = 'rag_pipeline', 
                log_file: Optional[str] = None,
                log_level: str = 'info',
                log_dir: str = None) -> logging.Logger:
    """
    设置并返回一个配置好的日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名，如果为None则使用name.log
        log_level: 日志级别，可选值：debug, info, warning, error, critical
        log_dir: 日志文件目录，默认为当前目录下的logs文件夹
        
    Returns:
        配置好的日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVELS.get(log_level.lower(), logging.INFO))
    
    # 如果已经有处理器，不重复添加
    if logger.handlers:
        return logger
    
    # 设置日志文件路径
    if log_dir is None:
        log_dir = os.path.join(os.getcwd(), 'logs')
    
    # 确保日志目录存在
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    if log_file is None:
        log_file = f"{name}.log"
    
    log_path = os.path.join(log_dir, log_file)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(LOG_LEVELS.get(log_level.lower(), logging.INFO))
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVELS.get(log_level.lower(), logging.INFO))
    
    # 设置格式化器
    file_formatter = logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
    console_formatter = ColoredFormatter("[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def log_exception(logger: Optional[logging.Logger] = None):
    """
    异常日志装饰器，用于捕获和记录函数执行过程中的异常
    
    Args:
        logger: 日志记录器，如果为None则使用默认记录器
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            nonlocal logger
            if logger is None:
                logger = logging.getLogger('rag_pipeline')
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 记录异常信息和堆栈跟踪
                error_msg = f"Exception in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                logger.debug(f"Traceback: {traceback.format_exc()}")
                # 重新抛出异常
                raise
        return wrapper
    return decorator


# 创建默认日志记录器
logger = setup_logger('rag_pipeline', log_file='app.log')

# 记录日志系统初始化成功
logger.info("日志系统初始化成功")
