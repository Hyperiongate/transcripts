"""
Job Storage Module - Handles job tracking and results storage
Simplified version that works with your existing config
"""
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from config import Config

class InMemoryJobStorage:
    """In-memory storage for jobs and results"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
    def create_job(self, job_id: str, initial_data: Dict[str, Any]) -> None:
        """Create a new job"""
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'status': 'created',
                'progress': 0,
                **initial_data
            }
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update job status"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(updates)
                self.jobs[job_id]['updated_at'] = datetime.utcnow().isoformat()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def store_results(self, job_id: str, results: Dict[str, Any]) -> None:
        """Store job results"""
        with self.lock:
            self.results[job_id] = {
                'job_id': job_id,
                'stored_at': datetime.utcnow().isoformat(),
                **results
            }
    
    def get_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get results by job ID"""
        with self.lock:
            return self.results.get(job_id)
    
    def cleanup_old_jobs(self, hours: int = 24) -> None:
        """Remove jobs older than specified hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self.lock:
            # Clean up old jobs
            old_job_ids = []
            for job_id, job in self.jobs.items():
                created = datetime.fromisoformat(job['created_at'])
                if created < cutoff:
                    old_job_ids.append(job_id)
            
            for job_id in old_job_ids:
                self.jobs.pop(job_id, None)
                self.results.pop(job_id, None)


# MongoDB storage implementation (optional, only if MongoDB is configured)
try:
    from pymongo import MongoClient
    has_mongodb = True
except ImportError:
    has_mongodb = False

class MongoJobStorage:
    """MongoDB-based storage for jobs and results"""
    
    def __init__(self, uri: str, db_name: str):
        if not has_mongodb:
            raise ImportError("pymongo not installed")
        
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.jobs_collection = self.db.jobs
        self.results_collection = self.db.results
    
    def create_job(self, job_id: str, initial_data: Dict[str, Any]) -> None:
        """Create a new job"""
        job_data = {
            '_id': job_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'status': 'created',
            'progress': 0,
            **initial_data
        }
        self.jobs_collection.insert_one(job_data)
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update job status"""
        updates['updated_at'] = datetime.utcnow()
        self.jobs_collection.update_one(
            {'_id': job_id},
            {'$set': updates}
        )
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        job = self.jobs_collection.find_one({'_id': job_id})
        if job:
            job['id'] = job.pop('_id')
            # Convert datetime objects to ISO format strings
            if isinstance(job.get('created_at'), datetime):
                job['created_at'] = job['created_at'].isoformat()
            if isinstance(job.get('updated_at'), datetime):
                job['updated_at'] = job['updated_at'].isoformat()
        return job
    
    def store_results(self, job_id: str, results: Dict[str, Any]) -> None:
        """Store job results"""
        results_data = {
            '_id': job_id,
            'stored_at': datetime.utcnow(),
            **results
        }
        self.results_collection.replace_one(
            {'_id': job_id},
            results_data,
            upsert=True
        )
    
    def get_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get results by job ID"""
        results = self.results_collection.find_one({'_id': job_id})
        if results:
            results['job_id'] = results.pop('_id')
            # Convert datetime objects to ISO format strings
            if isinstance(results.get('stored_at'), datetime):
                results['stored_at'] = results['stored_at'].isoformat()
        return results
    
    def cleanup_old_jobs(self, hours: int = 24) -> None:
        """Remove jobs older than specified hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Get old job IDs
        old_jobs = self.jobs_collection.find(
            {'created_at': {'$lt': cutoff}},
            {'_id': 1}
        )
        old_job_ids = [job['_id'] for job in old_jobs]
        
        # Delete old jobs and results
        if old_job_ids:
            self.jobs_collection.delete_many({'_id': {'$in': old_job_ids}})
            self.results_collection.delete_many({'_id': {'$in': old_job_ids}})


# Singleton instance
_storage_instance = None
_storage_lock = threading.Lock()


def get_job_storage():
    """Get the job storage instance (singleton)"""
    global _storage_instance
    
    with _storage_lock:
        if _storage_instance is None:
            # Check configuration to determine storage type
            if Config.JOB_STORAGE_TYPE == 'mongodb' and Config.MONGODB_URI and has_mongodb:
                try:
                    _storage_instance = MongoJobStorage(
                        Config.MONGODB_URI,
                        Config.MONGODB_DB_NAME
                    )
                    print("Using MongoDB for job storage")
                except Exception as e:
                    print(f"Failed to connect to MongoDB: {e}")
                    print("Falling back to in-memory storage")
                    _storage_instance = InMemoryJobStorage()
            else:
                print("Using in-memory job storage")
                _storage_instance = InMemoryJobStorage()
    
    return _storage_instance


# Background cleanup task
def start_cleanup_task(interval_hours: int = 1):
    """Start a background task to clean up old jobs"""
    import time
    
    def cleanup_loop():
        storage = get_job_storage()
        while True:
            try:
                storage.cleanup_old_jobs(Config.JOB_RETENTION_HOURS)
            except Exception as e:
                print(f"Error in cleanup task: {e}")
            
            # Sleep for the interval
            time.sleep(interval_hours * 3600)
    
    # Start in a daemon thread
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()


# Start cleanup on import (optional)
if os.environ.get('AUTO_CLEANUP', 'true').lower() == 'true':
    start_cleanup_task()
