# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Docker Container Management Utilities
======================================

Intelligent container orchestration for AMP platform microservices.

Core Features:
1. Container status query and health checking
2. On-demand service startup/shutdown for resource optimization
3. Resource monitoring (VRAM/Memory/CPU usage)
4. Batch operations and log retrieval

Architecture:
- DockerManager: Main orchestration class with health check support
- Service configuration table: Container name -> Port mapping + Health endpoint
- Global singleton pattern for cross-module access

Supported Services:
- amp-designer (8001): AMP sequence generator
- amp-hydramp (8008): Hydrophobicity predictor
- amp-diff-amp (8009): Differential AMP generator
- amp-macrel (8002): AMP activity classifier
- amp-mic (8003): MIC value predictor
- amp-hemolysis (8004): Hemolysis predictor
- amp-cpp (8005): Cell-penetrating peptide predictor
- amp-structure (8006): 3D structure prediction service

Usage:
    >>> from docker_utils import get_docker_manager
    >>> dm = get_docker_manager()
    >>> dm.start_service("amp-designer")
    >>> dm.get_container_status("amp-designer")
    'running'

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""
import docker
import time
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DockerManager:
    """
    Docker container orchestration manager for AMP platform microservices.
    
    Provides intelligent container lifecycle management with health checking,
    resource optimization, and batch operations support.
    
    Attributes:
        client: Docker SDK client instance (from docker.from_env())
        available: Whether Docker daemon is accessible
        service_config: Service configuration table
            Keys: Container name (str)
            Values: Dict with keys:
                - port: Service port (int)
                - health_path: Health check endpoint (str)
                - startup_time: Expected startup duration in seconds (int)
    
    Service Configuration:
        - amp-designer: Port 8001, startup 10s
        - amp-hydramp: Port 8008, startup 15s
        - amp-diff-amp: Port 8009, startup 20s
        - amp-macrel: Port 8002, startup 5s
        - amp-mic: Port 8003, startup 12s
        - amp-hemolysis: Port 8004, startup 12s
        - amp-cpp: Port 8005, startup 12s
        - amp-structure: Port 8006, startup 25s
    
    Examples:
        >>> dm = DockerManager()
        >>> dm.start_service("amp-designer", wait_for_health=True)
        True
        >>> dm.get_container_status("amp-designer")
        'running'
        >>> dm.stop_service("amp-designer")
        True
    """
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.available = True
            logger.info("✅ Docker client initialized successfully")
        except Exception as e:
            self.available = False
            self.client = None
            logger.error(f"❌ Docker client initialization failed: {e}")
        
        # Service configuration table (container name -> port mapping)
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
        """
        Query container running status.
        
        Args:
            service_name: Container name (e.g., "amp-designer")
        
        Returns:
            Container status string:
                - 'running': Container is running
                - 'exited': Container has stopped
                - 'paused': Container is paused
                - 'created': Container created but not started
                - None: Container not found or Docker unavailable
        
        Examples:
            >>> dm.get_container_status("amp-designer")
            'running'
            >>> dm.get_container_status("non-existent")
            None
        """
        if not self.available:
            return None
        
        try:
            container = self.client.containers.get(service_name)
            return container.status
        except docker.errors.NotFound:
            logger.warning(f"⚠️ Container {service_name} does not exist")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to query container status: {e}")
            return None

    def start_service(self, service_name: str, wait_for_health: bool = True, timeout: int = 120) -> bool:
        """
        Start container and wait for health check to pass.
        
        Args:
            service_name: Container name (e.g., 'amp-designer')
            wait_for_health: Whether to wait for health check (default: True)
            timeout: Health check timeout in seconds (default: 120)
        
        Returns:
            True if startup successful (and health check passed if enabled)
            False otherwise
        
        Side Effects:
            - Starts Docker container if not running
            - Waits for configured startup_time before health check
            - Logs startup progress and health check results
        
        Examples:
            >>> dm.start_service("amp-designer")
            True
            >>> dm.start_service("amp-mic", wait_for_health=False)
            True
        """
        if not self.available:
            logger.warning("Docker unavailable, skipping container startup")
            return False
        
        try:
            container = self.client.containers.get(service_name)
            
            # If already running, return immediately
            if container.status == 'running':
                logger.info(f"✅ {service_name} is already running")
                return True
            
            logger.info(f"🚀 Starting {service_name}...")
            container.start()
            
            # Wait for startup
            config = self.service_config.get(service_name, {})
            startup_time = config.get("startup_time", 10)
            time.sleep(startup_time)
            
            # Health check
            if wait_for_health:
                if self._wait_for_health(service_name, timeout):
                    logger.info(f"✅ {service_name} started successfully and passed health check")
                    return True
                else:
                    logger.warning(f"⚠️ {service_name} started but failed health check")
                    return False
            
            return True
            
        except docker.errors.NotFound:
            logger.error(f"❌ Container {service_name} not found, check docker-compose.yml")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start {service_name}: {e}")
            return False

    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """
        Stop container to release resources.
        
        Args:
            service_name: Container name
            force: Whether to force stop (kill) instead of graceful shutdown
        
        Returns:
            True if stop successful, False otherwise
        
        Examples:
            >>> dm.stop_service("amp-designer")
            True
            >>> dm.stop_service("amp-mic", force=True)
            True
        """
        if not self.available:
            return False
        
        try:
            container = self.client.containers.get(service_name)
            
            if container.status != 'running':
                logger.info(f"ℹ️ {service_name} is already stopped")
                return True
            
            logger.info(f"🛑 Stopping {service_name}...")
            
            if force:
                container.kill()
            else:
                container.stop(timeout=10)
            
            logger.info(f"✅ {service_name} stopped")
            return True
            
        except docker.errors.NotFound:
            logger.warning(f"⚠️ Container {service_name} does not exist")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to stop {service_name}: {e}")
            return False

    def restart_service(self, service_name: str) -> bool:
        """
        Restart service container (stop + start).
        
        Args:
            service_name: Container name
        
        Returns:
            True if restart successful, False otherwise
        
        Examples:
            >>> dm.restart_service("amp-designer")
            True
        """
        logger.info(f"🔄 Restarting {service_name}...")
        if self.stop_service(service_name):
            time.sleep(2)
            return self.start_service(service_name)
        return False

    def _wait_for_health(self, service_name: str, timeout: int = 120) -> bool:
        """
        Wait for health check to pass via HTTP endpoint.
        
        Args:
            service_name: Container name
            timeout: Maximum wait time in seconds (default: 120)
        
        Returns:
            True if health check passed within timeout, False otherwise
        
        Notes:
            - Uses HTTP GET to {service_name}:{port}{health_path}
            - Expects 200 status code for healthy state
            - Retries every 3 seconds until timeout
            - Works within Docker network (container name resolution)
        
        Examples:
            >>> dm._wait_for_health("amp-designer", timeout=60)
            True
        """
        config = self.service_config.get(service_name)
        if not config:
            return True  # No config = assume healthy
        
        port = config.get("port")
        health_path = config.get("health_path", "/health")
        
        # Build health check URL (use container name in Docker network)
        health_url = f"http://{service_name}:{port}{health_path}"
        
        start_time = time.time()
        retry_count = 0
        
        while time.time() - start_time < timeout:
            try:
                # Note: Requires Docker network access
                # Use localhost + mapped port from host machine
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    logger.info(f"✅ {service_name} health check passed (attempt {retry_count + 1})")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            retry_count += 1
            time.sleep(3)
        
        logger.warning(f"⚠️ {service_name} health check timeout ({timeout}s)")
        return False

    def get_all_services_status(self) -> Dict[str, str]:
        """
        Query status of all configured services.
        
        Returns:
            Dictionary mapping service names to status strings:
                {"amp-designer": "running", "amp-mic": "exited", ...}
            Empty dict if Docker unavailable
        
        Examples:
            >>> dm.get_all_services_status()
            {'amp-designer': 'running', 'amp-mic': 'exited', ...}
        """
        if not self.available:
            return {}
        
        status_dict = {}
        for service_name in self.service_config.keys():
            status = self.get_container_status(service_name)
            status_dict[service_name] = status or "not_found"
        
        return status_dict

    def batch_start(self, service_names: List[str]) -> Dict[str, bool]:
        """
        Start multiple services in batch (without waiting for health checks).
        
        Args:
            service_names: List of container names to start
        
        Returns:
            Dictionary mapping service names to success status:
                {"amp-designer": True, "amp-mic": False, ...}
        
        Examples:
            >>> dm.batch_start(["amp-designer", "amp-mic"])
            {'amp-designer': True, 'amp-mic': True}
        """
        results = {}
        for name in service_names:
            results[name] = self.start_service(name, wait_for_health=False)
        return results

    def batch_stop(self, service_names: List[str]) -> Dict[str, bool]:
        """
        Stop multiple services in batch.
        
        Args:
            service_names: List of container names to stop
        
        Returns:
            Dictionary mapping service names to success status:
                {"amp-designer": True, "amp-mic": True, ...}
        
        Examples:
            >>> dm.batch_stop(["amp-designer", "amp-mic"])
            {'amp-designer': True, 'amp-mic': True}
        """
        results = {}
        for name in service_names:
            results[name] = self.stop_service(name)
        return results

    def get_container_logs(self, service_name: str, tail: int = 50) -> Optional[str]:
        """
        Retrieve container logs for debugging.
        
        Args:
            service_name: Container name
            tail: Number of recent log lines to retrieve (default: 50)
        
        Returns:
            Log content as string (UTF-8 decoded)
            None if Docker unavailable or retrieval failed
        
        Examples:
            >>> logs = dm.get_container_logs("amp-designer", tail=20)
            >>> print(logs)
            2025-01-13T10:23:45.123Z Starting AMP Designer service...
            ...
        """
        if not self.available:
            return None
        
        try:
            container = self.client.containers.get(service_name)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Failed to retrieve logs: {e}")
            return None


# ======================
# Global Singleton
# ======================
_docker_manager = None

def get_docker_manager() -> DockerManager:
    """
    Get or create global DockerManager singleton.
    
    Returns:
        Global DockerManager instance
    
    Examples:
        >>> dm = get_docker_manager()
        >>> dm.start_service("amp-designer")
        True
    """
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerManager()
    return _docker_manager