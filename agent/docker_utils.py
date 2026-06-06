# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""Docker 容器智能管理工具
====================================
核心功能:
1. 容器状态查询与健康检查
2. 按需启动/停止服务容器
3. 资源监控(显存/内存/CPU占用)
4. 支持批量操作与日志查询
"""
import docker
import time
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DockerManager:
    """Docker 容器管理器 - 为 Qwen Agent 提供容器编排能力"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.available = True
            logger.info("✅ Docker 客户端初始化成功")
        except Exception as e:
            self.available = False
            self.client = None
            logger.error(f"❌ Docker 客户端初始化失败: {e}")
        
        # 服务配置表 (容器名 -> 端口映射)
        self.service_config = {
            "amp-designer": {"port": 8001, "health_path": "/health", "startup_time": 10},
            "amp-hydramp": {"port": 8008, "health_path": "/health", "startup_time": 15},
            "amp-diff-amp": {"port": 8009, "health_path": "/health", "startup_time": 20},
            "amp-macrel": {"port": 8002, "health_path": "/health", "startup_time": 5},
            "amp-mic": {"port": 8003, "health_path": "/health", "startup_time": 12},
            "amp-hemolysis": {"port": 8004, "health_path": "/health", "startup_time": 12},
            "amp-cpp": {"port": 8005, "health_path": "/health", "startup_time": 12},
            "amp-structure": {"port": 8006, "health_path": "/health", "startup_time": 25}
        }

    def get_container_status(self, service_name: str) -> Optional[str]:
        """获取容器运行状态
        
        Returns:
            'running' | 'exited' | 'paused' | 'created' | None
        """
        if not self.available:
            return None
        
        try:
            container = self.client.containers.get(service_name)
            return container.status
        except docker.errors.NotFound:
            logger.warning(f"⚠️ 容器 {service_name} 不存在")
            return None
        except Exception as e:
            logger.error(f"❌ 查询容器状态失败: {e}")
            return None

    def start_service(self, service_name: str, wait_for_health: bool = True, timeout: int = 120) -> bool:
        """启动容器并等待健康检查通过
        
        Args:
            service_name: 容器名称 (如 'amp-designer')
            wait_for_health: 是否等待健康检查
            timeout: 健康检查超时时间(秒)
            
        Returns:
            bool: 启动成功返回 True
        """
        if not self.available:
            logger.warning("Docker 不可用,跳过容器启动")
            return False
        
        try:
            container = self.client.containers.get(service_name)
            
            # 如果已经在运行,直接返回
            if container.status == 'running':
                logger.info(f"✅ {service_name} 已在运行")
                return True
            
            logger.info(f"🚀 正在启动 {service_name}...")
            container.start()
            
            # 等待启动
            config = self.service_config.get(service_name, {})
            startup_time = config.get("startup_time", 10)
            time.sleep(startup_time)
            
            # 健康检查
            if wait_for_health:
                if self._wait_for_health(service_name, timeout):
                    logger.info(f"✅ {service_name} 启动成功并通过健康检查")
                    return True
                else:
                    logger.warning(f"⚠️ {service_name} 启动但未通过健康检查")
                    return False
            
            return True
            
        except docker.errors.NotFound:
            logger.error(f"❌ 容器 {service_name} 不存在,请检查 docker-compose.yml")
            return False
        except Exception as e:
            logger.error(f"❌ 启动 {service_name} 失败: {e}")
            return False

    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """停止容器释放资源
        
        Args:
            service_name: 容器名称
            force: 是否强制停止(kill)
            
        Returns:
            bool: 停止成功返回 True
        """
        if not self.available:
            return False
        
        try:
            container = self.client.containers.get(service_name)
            
            if container.status != 'running':
                logger.info(f"ℹ️ {service_name} 已停止")
                return True
            
            logger.info(f"🛑 正在停止 {service_name}...")
            
            if force:
                container.kill()
            else:
                container.stop(timeout=10)
            
            logger.info(f"✅ {service_name} 已停止")
            return True
            
        except docker.errors.NotFound:
            logger.warning(f"⚠️ 容器 {service_name} 不存在")
            return False
        except Exception as e:
            logger.error(f"❌ 停止 {service_name} 失败: {e}")
            return False

    def restart_service(self, service_name: str) -> bool:
        """重启服务容器"""
        logger.info(f"🔄 正在重启 {service_name}...")
        if self.stop_service(service_name):
            time.sleep(2)
            return self.start_service(service_name)
        return False

    def _wait_for_health(self, service_name: str, timeout: int = 120) -> bool:
        """等待健康检查通过
        
        通过 HTTP 请求验证服务是否就绪
        """
        config = self.service_config.get(service_name)
        if not config:
            return True  # 没有配置的服务默认认为健康
        
        port = config.get("port")
        health_path = config.get("health_path", "/health")
        
        # 构造健康检查 URL (在 Docker 网络内使用容器名)
        health_url = f"http://{service_name}:{port}{health_path}"
        
        start_time = time.time()
        retry_count = 0
        
        while time.time() - start_time < timeout:
            try:
                # 注意: 这里需要在 Docker 网络内才能访问
                # 如果从宿主机调用,需要用 localhost 和映射端口
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    logger.info(f"✅ {service_name} 健康检查通过 (尝试 {retry_count + 1} 次)")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            retry_count += 1
            time.sleep(3)
        
        logger.warning(f"⚠️ {service_name} 健康检查超时 ({timeout}秒)")
        return False

    def get_all_services_status(self) -> Dict[str, str]:
        """获取所有服务的状态
        
        Returns:
            Dict: {service_name: status}
        """
        if not self.available:
            return {}
        
        status_dict = {}
        for service_name in self.service_config.keys():
            status = self.get_container_status(service_name)
            status_dict[service_name] = status or "not_found"
        
        return status_dict

    def batch_start(self, service_names: List[str]) -> Dict[str, bool]:
        """批量启动服务
        
        Returns:
            Dict: {service_name: success}
        """
        results = {}
        for name in service_names:
            results[name] = self.start_service(name, wait_for_health=False)
        return results

    def batch_stop(self, service_names: List[str]) -> Dict[str, bool]:
        """批量停止服务"""
        results = {}
        for name in service_names:
            results[name] = self.stop_service(name)
        return results

    def get_container_logs(self, service_name: str, tail: int = 50) -> Optional[str]:
        """获取容器日志
        
        Args:
            service_name: 容器名称
            tail: 显示最后 N 行日志
            
        Returns:
            str: 日志内容
        """
        if not self.available:
            return None
        
        try:
            container = self.client.containers.get(service_name)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8')
        except Exception as e:
            logger.error(f"❌ 获取日志失败: {e}")
            return None


# ======================
# 全局单例
# ======================
_docker_manager = None

def get_docker_manager() -> DockerManager:
    """获取 DockerManager 单例"""
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerManager()
    return _docker_manager