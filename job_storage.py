"""
Job Storage Service
Handles storage and retrieval of analysis jobs
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class JobStorage:
    """Simple in-memory job storage"""
    
    def __init__(self):
        self.jobs = {}
        self.max_age = timedelta(hours=24)
    
    def set(self, job_id: str, data: Dict) -> None:
        """Store job data"""
        self.jobs[job_id] = {
            'data': data,
            'created_at': datetime.now()
        }
        self._cleanup_old_jobs()
    
    def get(self, job_id: str) -> Optional[Dict]:
        """Retrieve job data"""
        if job_id in self.jobs:
            return self.jobs[job_id]['data']
        return None
    
    def update(self, job_id: str, updates: Dict) -> None:
        """Update job data"""
        if job_id in self.jobs:
            self.jobs[job_id]['data'].update(updates)
            self.jobs[job_id]['updated_at'] = datetime.now()
    
    def delete(self, job_id: str) -> None:
        """Delete job data"""
        if job_id in self.jobs:
            del self.jobs[job_id]
    
    def _cleanup_old_jobs(self) -> None:
        """Remove jobs older than max_age"""
        current_time = datetime.now()
        jobs_to_delete = []
        
        for job_id, job_info in self.jobs.items():
            if current_time - job_info['created_at'] > self.max_age:
                jobs_to_delete.append(job_id)
        
        for job_id in jobs_to_delete:
            del self.jobs[job_id]
        
        if jobs_to_delete:
            logger.info(f"Cleaned up {len(jobs_to_delete)} old jobs")
    
    def get_all_jobs(self) -> Dict[str, Dict]:
        """Get all jobs (for debugging)"""
        return {
            job_id: job_info['data'] 
            for job_id, job_info in self.jobs.items()
        }
    
    def get_stats(self) -> Dict:
        """Get storage statistics"""
        return {
            'total_jobs': len(self.jobs),
            'active_jobs': sum(
                1 for job in self.jobs.values() 
                if job['data'].get('status') == 'processing'
            ),
            'completed_jobs': sum(
                1 for job in self.jobs.values() 
                if job['data'].get('status') == 'completed'
            ),
            'failed_jobs': sum(
                1 for job in self.jobs.values() 
                if job['data'].get('status') == 'failed'
            )
        }
