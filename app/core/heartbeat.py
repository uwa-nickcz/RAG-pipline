# -*- coding: utf-8 -*-
"""
心跳检测模块 - 提供稳定的连接保活和监控机制
"""
import asyncio
import time
import threading
from typing import Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from logger import logger


class ConnectionState(Enum):
    """连接状态枚举"""
    ACTIVE = "active"
    IDLE = "idle"
    TIMEOUT = "timeout"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    created_at: float
    last_activity: float
    state: ConnectionState = ConnectionState.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_count: int = 0
    heartbeat_count: int = 0


class HeartbeatMonitor:
    """心跳监控器 - 监控和管理连接状态"""
    
    def __init__(
        self,
        heartbeat_interval: float = 15.0,
        timeout_threshold: float = 300.0,
        cleanup_interval: float = 60.0,
        max_error_count: int = 5
    ):
        """
        初始化心跳监控器
        
        Args:
            heartbeat_interval: 心跳间隔（秒）
            timeout_threshold: 超时阈值（秒）
            cleanup_interval: 清理间隔（秒）
            max_error_count: 最大错误次数
        """
        self.heartbeat_interval = heartbeat_interval
        self.timeout_threshold = timeout_threshold
        self.cleanup_interval = cleanup_interval
        self.max_error_count = max_error_count
        
        self.connections: Dict[str, ConnectionInfo] = {}
        self.callbacks: Dict[str, Callable] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动心跳监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("心跳监控器已启动")
    
    async def stop(self):
        """停止心跳监控"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("心跳监控器已停止")
    
    async def register_connection(
        self,
        connection_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        on_timeout: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ):
        """
        注册连接
        
        Args:
            connection_id: 连接ID
            metadata: 连接元数据
            on_timeout: 超时回调
            on_error: 错误回调
        """
        async with self._lock:
            current_time = time.time()
            self.connections[connection_id] = ConnectionInfo(
                connection_id=connection_id,
                created_at=current_time,
                last_activity=current_time,
                metadata=metadata or {}
            )
            
            # 注册回调
            if on_timeout:
                self.callbacks[f"{connection_id}_timeout"] = on_timeout
            if on_error:
                self.callbacks[f"{connection_id}_error"] = on_error
        
        logger.debug(f"连接已注册: {connection_id}")
    
    async def update_activity(self, connection_id: str):
        """
        更新连接活动时间
        
        Args:
            connection_id: 连接ID
        """
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].last_activity = time.time()
                self.connections[connection_id].state = ConnectionState.ACTIVE
                # 重置错误计数
                self.connections[connection_id].error_count = 0
    
    async def report_error(self, connection_id: str, error: Exception):
        """
        报告连接错误
        
        Args:
            connection_id: 连接ID
            error: 错误信息
        """
        async with self._lock:
            if connection_id in self.connections:
                conn_info = self.connections[connection_id]
                conn_info.error_count += 1
                conn_info.state = ConnectionState.ERROR
                
                logger.warning(f"连接 {connection_id} 发生错误: {str(error)}")
                
                # 检查是否超过最大错误次数
                if conn_info.error_count >= self.max_error_count:
                    await self._handle_connection_failure(connection_id)
                
                # 调用错误回调
                error_callback = self.callbacks.get(f"{connection_id}_error")
                if error_callback:
                    try:
                        await error_callback(connection_id, error)
                    except Exception as e:
                        logger.error(f"执行错误回调失败: {str(e)}")
    
    async def unregister_connection(self, connection_id: str):
        """
        注销连接
        
        Args:
            connection_id: 连接ID
        """
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].state = ConnectionState.CLOSED
                del self.connections[connection_id]
                
                # 清理回调
                self.callbacks.pop(f"{connection_id}_timeout", None)
                self.callbacks.pop(f"{connection_id}_error", None)
        
        logger.debug(f"连接已注销: {connection_id}")
    
    def should_send_heartbeat(self, connection_id: str) -> bool:
        """
        检查是否应该发送心跳
        
        Args:
            connection_id: 连接ID
            
        Returns:
            是否需要发送心跳
        """
        if connection_id not in self.connections:
            return False
        
        conn_info = self.connections[connection_id]
        current_time = time.time()
        
        return (current_time - conn_info.last_activity) > self.heartbeat_interval
    
    async def send_heartbeat(self, connection_id: str):
        """
        发送心跳
        
        Args:
            connection_id: 连接ID
        """
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].heartbeat_count += 1
                self.connections[connection_id].last_activity = time.time()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        获取连接统计信息
        
        Returns:
            连接统计信息
        """
        current_time = time.time()
        stats = {
            "total_connections": len(self.connections),
            "active_connections": 0,
            "idle_connections": 0,
            "error_connections": 0,
            "average_duration": 0,
            "total_heartbeats": 0
        }
        
        if not self.connections:
            return stats
        
        total_duration = 0
        for conn_info in self.connections.values():
            duration = current_time - conn_info.created_at
            total_duration += duration
            stats["total_heartbeats"] += conn_info.heartbeat_count
            
            if conn_info.state == ConnectionState.ACTIVE:
                stats["active_connections"] += 1
            elif conn_info.state == ConnectionState.IDLE:
                stats["idle_connections"] += 1
            elif conn_info.state == ConnectionState.ERROR:
                stats["error_connections"] += 1
        
        stats["average_duration"] = total_duration / len(self.connections)
        return stats
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await self._check_connections()
                await asyncio.sleep(self.heartbeat_interval / 2)  # 更频繁的检查
            except Exception as e:
                logger.error(f"心跳监控循环错误: {str(e)}")
                await asyncio.sleep(1)
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            try:
                await self._cleanup_stale_connections()
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"清理循环错误: {str(e)}")
                await asyncio.sleep(5)
    
    async def _check_connections(self):
        """检查连接状态"""
        current_time = time.time()
        timeout_connections = []
        
        async with self._lock:
            for connection_id, conn_info in self.connections.items():
                # 检查超时
                if (current_time - conn_info.last_activity) > self.timeout_threshold:
                    if conn_info.state != ConnectionState.TIMEOUT:
                        conn_info.state = ConnectionState.TIMEOUT
                        timeout_connections.append(connection_id)
                # 检查空闲状态
                elif (current_time - conn_info.last_activity) > self.heartbeat_interval:
                    if conn_info.state == ConnectionState.ACTIVE:
                        conn_info.state = ConnectionState.IDLE
        
        # 处理超时连接
        for connection_id in timeout_connections:
            await self._handle_connection_timeout(connection_id)
    
    async def _handle_connection_timeout(self, connection_id: str):
        """处理连接超时"""
        logger.warning(f"连接超时: {connection_id}")
        
        # 调用超时回调
        timeout_callback = self.callbacks.get(f"{connection_id}_timeout")
        if timeout_callback:
            try:
                await timeout_callback(connection_id)
            except Exception as e:
                logger.error(f"执行超时回调失败: {str(e)}")
    
    async def _handle_connection_failure(self, connection_id: str):
        """处理连接失败"""
        logger.error(f"连接失败，错误次数过多: {connection_id}")
        await self.unregister_connection(connection_id)
    
    async def _cleanup_stale_connections(self):
        """清理过期连接"""
        current_time = time.time()
        stale_connections = []
        
        async with self._lock:
            for connection_id, conn_info in self.connections.items():
                # 清理长时间超时的连接
                if (conn_info.state == ConnectionState.TIMEOUT and
                    (current_time - conn_info.last_activity) > (self.timeout_threshold * 2)):
                    stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            await self.unregister_connection(connection_id)
            logger.info(f"清理过期连接: {connection_id}")


class GlobalHeartbeatManager:
    """全局心跳管理器 - 单例模式"""
    
    _instance: Optional['GlobalHeartbeatManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.monitor = HeartbeatMonitor()
            self._initialized = True
    
    async def start(self):
        """启动全局心跳监控"""
        await self.monitor.start()
    
    async def stop(self):
        """停止全局心跳监控"""
        await self.monitor.stop()
    
    def get_monitor(self) -> HeartbeatMonitor:
        """获取心跳监控器实例"""
        return self.monitor


# 全局心跳管理器实例
global_heartbeat_manager = GlobalHeartbeatManager()