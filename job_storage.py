"""
Job Storage Manager - Handles job persistence with Redis support and fallback
"""
import os
import json
import logging
import threading
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class JobStorage:
    """Abstract base class for job storage"""
    
    def set(self, job_id: str, job_data: Dict[str, Any]) -> None:
        raise NotImplementedError
    
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    def update(self, job_id: str, updates: Dict[str, Any]) -> None:
        raise NotImplementedError
    
    def delete(self, job_id: str) -> None:
        raise NotImplementedError
    
    def exists(self, job_id: str) -> bool:
        raise NotImplementedError
    
    def list_jobs(self) -> list:
        raise NotImplementedError


class InMemoryJobStorage(JobStorage):
    """Thread-safe in-memory job storage for development"""
    
    def __init__(self):
        self._jobs = {}
        self._lock = threading.RLock()
        logger.info("Using in-memory job storage (development mode)")
    
    def set(self, job_id: str, job_data: Dict[str, Any]) -> None:
        with self._lock:
            self._jobs[job_id] = job_data.copy()
    
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._jobs.get(job_id, {}).copy() if job_id in self._jobs else None
    
    def update(self, job_id: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(updates)
            else:
                logger.warning(f"Attempted to update non-existent job: {job_id}")
    
    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
    
    def exists(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._jobs
    
    def list_jobs(self) -> list:
        with self._lock:
            return list(self._jobs.keys())


class RedisJobStorage(JobStorage):
    """Redis-based job storage for production"""
    
    def __init__(self, redis_url: str = None):
        try:
            import redis
            self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
            self.ttl = 3600  # 1 hour TTL for jobs
            logger.info(f"Connected to Redis at {self._sanitize_url(self.redis_url)}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    def _sanitize_url(self, url: str) -> str:
        """Remove password from Redis URL for logging"""
        if '@' in url:
            parts = url.split('@')
            return parts[0].split('//')[0] + '//*****@' + parts[1]
        return url
    
    def _key(self, job_id: str) -> str:
        """Generate Redis key for job"""
        return f"job:{job_id}"
    
    def set(self, job_id: str, job_data: Dict[str, Any]) -> None:
        try:
            key = self._key(job_id)
            self.redis_client.setex(key, self.ttl, json.dumps(job_data))
        except Exception as e:
            logger.error(f"Redis set error for job {job_id}: {str(e)}")
            raise
    
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._key(job_id)
            data = self.redis_client.get(key)
            if data:
                # Reset TTL on access to keep active jobs alive
                self.redis_client.expire(key, self.ttl)
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error for job {job_id}: {str(e)}")
            return None
    
    def update(self, job_id: str, updates: Dict[str, Any]) -> None:
        try:
            job_data = self.get(job_id)
            if job_data:
                job_data.update(updates)
                self.set(job_id, job_data)
            else:
                logger.warning(f"Attempted to update non-existent job: {job_id}")
        except Exception as e:
            logger.error(f"Redis update error for job {job_id}: {str(e)}")
            raise
    
    def delete(self, job_id: str) -> None:
        try:
            self.redis_client.delete(self._key(job_id))
        except Exception as e:
            logger.error(f"Redis delete error for job {job_id}: {str(e)}")
    
    def exists(self, job_id: str) -> bool:
        try:
            return bool(self.redis_client.exists(self._key(job_id)))
        except Exception as e:
            logger.error(f"Redis exists error for job {job_id}: {str(e)}")
            return False
    
    def list_jobs(self) -> list:
        try:
            keys = self.redis_client.keys("job:*")
            return [key.split(":", 1)[1] for key in keys]
        except Exception as e:
            logger.error(f"Redis list_jobs error: {str(e)}")
            return []


class JobStorageManager:
    """Factory class to create appropriate job storage"""
    
    _instance = None
    _storage = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobStorageManager, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_storage(cls) -> JobStorage:
        """Get or create job storage instance"""
        if cls._storage is None:
            # Try Redis first if URL is available
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                try:
                    cls._storage = RedisJobStorage(redis_url)
                    logger.info("Using Redis job storage")
                except Exception as e:
                    logger.warning(f"Failed to initialize Redis storage: {str(e)}")
                    logger.info("Falling back to in-memory storage")
                    cls._storage = InMemoryJobStorage()
            else:
                # Use in-memory storage for development
                cls._storage = InMemoryJobStorage()
        
        return cls._storage


# Convenience function for easy import
def get_job_storage() -> JobStorage:
    """Get the configured job storage instance"""
    return JobStorageManager.get_storage()
