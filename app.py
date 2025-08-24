"""
Main Flask Application for Political Fact Checker
Updated with enhanced verification system and insights
"""
import os
import json
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
CORS(app)

# Configuration
class Config:
    # Required API keys - update in Render
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_FACTCHECK_API_KEY = os.getenv('GOOGLE_FACTCHECK_API_KEY')
    NEWS_API_KEY = os.getenv('NEWS_API_KEY')
    SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY')
    SCRAPINGBEE_API_KEY = os.getenv('SCRAPINGBEE_API_KEY')
    WOLFRAM_ALPHA_API_KEY = os.getenv('WOLFRAM_ALPHA_API_KEY')
    FRED_API_KEY = os.getenv('FRED_API_KEY')
    MEDIASTACK_API_KEY = os.getenv('MEDIASTACK_API_KEY')
    NOAA_TOKEN = os.getenv('NOAA_TOKEN')
    CENSUS_API_KEY = os.getenv('CENSUS_API_KEY')
    CDC_API_KEY = os.getenv('CDC_API_KEY')
    
    # Model config
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    USE_GPT4 = os.getenv('USE_GPT4', 'False').lower() == 'true'
    if USE_GPT4:
        OPENAI_MODEL = 'gpt-4'
    
    # File handling
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
    EXPORT_FOLDER = os.getenv('EXPORT_FOLDER', '/tmp/exports')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    
    # Optional storage
    MONGODB_URI = os.getenv('MONGODB_URI')
    REDIS_URL = os.getenv('REDIS_URL')

# Apply config
app.config.from_object(Config)

# Ensure directories exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.EXPORT_FOLDER, exist_ok=True)

# Storage setup
in_memory_jobs = {}
mongo_client = None
redis_client = None

# Try to connect to MongoDB if configured
if Config.MONGODB_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client.server_info()
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {str(e)}. Using in-memory storage.")
        mongo_client = None
else:
    logger.info("MongoDB URI not configured. Using in-memory storage.")

# Try to connect to Redis if configured
if Config.REDIS_URL:
    try:
        import redis
        redis_client = redis.from_url(Config.REDIS_URL, socket_connect_timeout=5)
        redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {str(e)}. Using in-memory storage.")
        redis_client = None
else:
    logger.info("Redis URL not configured. Using in-memory storage.")

# Import services - REQUIRED for app to function
try:
    from services.transcript import TranscriptProcessor
    from services.claims import ClaimExtractor
    from services.enhanced_factcheck import FactChecker, VERDICT_CATEGORIES
    
    # Initialize services
    transcript_processor = TranscriptProcessor()
    claim_extractor = ClaimExtractor(openai_api_key=Config.OPENAI_API_KEY)
    fact_checker = FactChecker(Config)
    logger.info("Services initialized successfully")
except ImportError as e:
    logger.error(f"CRITICAL: Failed to import required services: {str(e)}")
    logger.error("Please ensure services directory exists with required files")
    raise SystemExit(f"Cannot start application without services: {str(e)}")

# Enhanced speaker database
SPEAKER_DATABASE = {
    'donald trump': {
        'full_name': 'Donald J. Trump',
        'role': '45th and 47th President of the United States',
        'party': 'Republican',
        'known_for': 'Real estate, reality TV, politics'
    },
    'joe biden': {
        'full_name': 'Joseph R. Biden Jr.',
        'role': '46th President of the United States',
        'party': 'Democrat',
        'known_for': 'Long Senate career, Vice President under Obama'
    },
    'kamala harris': {
        'full_name': 'Kamala D. Harris',
        'role': 'Vice President of the United States (2021-2025)',
        'party': 'Democrat',
        'known_for': 'First female VP, former Senator from California'
    },
    'jd vance': {
        'full_name': 'James David Vance',
        'role': 'Vice President of the United States (2025-)',
        'party': 'Republican',
        'known_for': 'Author of Hillbilly Elegy, Senator from Ohio'
    }
}

# Job management functions
def create_job(transcript: str) -> str:
    """Create a new job"""
    job_id = str(uuid.uuid4())
    job_data = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Starting analysis...',
        'created': datetime.now().isoformat(),
        'transcript': transcript[:1000],  # Store preview
        'results': None
    }
    
    # Store job
    try:
        if mongo_client:
            mongo_client.factchecker.jobs.insert_one(job_data)
        elif redis_client:
            redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
        else:
            in_memory_jobs[job_id] = job_data
    except Exception as e:
        logger.error(f"Error storing job: {e}")
        in_memory_jobs[job_id] = job_data
    
    return job_id

def get_job(job_id: str) -> Optional[Dict]:
    """Get job data"""
    try:
        if mongo_client:
            job = mongo_client.factchecker.jobs.find_one({'id': job_id})
            return job if job else None
        elif redis_client:
            data = redis_client.get(f"job:{job_id}")
            return json.loads(data) if data else None
        else:
            return in_memory_jobs.get(job_id)
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        return in_memory_jobs.get(job_id)

def update_job(job_id: str, updates: Dict):
    """Update job data"""
    try:
        if mongo_client:
            mongo_client.factchecker.jobs.update_one(
                {'id': job_id},
                {'$set': updates}
            )
        elif redis_client:
            job_data = get_job(job_id)
            if job_data:
                job_data.update(updates)
                redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
        else:
            if job_id in in_memory_jobs:
                in_memory_jobs[job_id].update(updates)
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        if job_id in in_memory_jobs:
            in_memory_jobs[job_id].update(updates)

def update_job_progress(job_id: str, progress: int, message: str):
    """Update job progress"""
    update_job(job_id, {
        'progress': progress,
        'message': message,
        'status': 'failed' if progress < 0 else 'processing'
    })

def calculate_credibility_score_enhanced(fact_checks: List[Dict]) -> Dict:
    """Calculate overall credibility score with enhanced verdicts"""
    if not fact_checks:
        return {
            'score': 0,
            'label': 'No claims verified',
            'verdict_counts': {},
            'breakdown': {}
        }
    
    # Count each verdict type
    verdict_counts = {}
    total_score = 0
    scorable_claims = 0
    
    for fc in fact_checks:
        verdict = fc.get('verdict', 'unverifiable')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        # Get score for this verdict
        verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['unverifiable'])
        if verdict_info.get('score') is not None:
            total_score += verdict_info['score']
            scorable_claims += 1
    
    # Calculate weighted score
    if scorable_claims > 0:
        score = total_score / scorable_claims
    else:
        score = 50  # Default to middle if no scorable claims
    
    # Determine overall label based on new verdict system
    verified_false = verdict_counts.get('verified_false', 0)
    verified_true = verdict_counts.get('verified_true', 0)
    mostly_true = verdict_counts.get('mostly_true', 0)
    mostly_false = verdict_counts.get('mostly_false', 0)
    misleading = verdict_counts.get('misleading', 0)
    lacks_context = verdict_counts.get('lacks_context', 0)
    partially_accurate = verdict_counts.get('partially_accurate', 0)
    unverifiable = verdict_counts.get('unverifiable', 0)
    
    # Enhanced label determination
    if verified_true + mostly_true > 0 and verified_false + mostly_false + misleading == 0 and score >= 85:
        label = 'Highly Credible - Claims Verified'
    elif verified_true + mostly_true > verified_false + mostly_false + misleading and score >= 70:
        label = 'Generally Credible - Mostly Verified'
    elif misleading >= 2:
        label = 'Deceptive - Multiple Misleading Claims'
    elif lacks_context >= 2:
        label = 'Missing Context - Important Information Omitted'
    elif verified_false + mostly_false > verified_true + mostly_true:
        label = 'Not Credible - Multiple False Claims'
    elif unverifiable > (verified_true + verified_false):
        label = 'Difficult to Verify - Limited Evidence'
    elif partially_accurate > (verified_true + verified_false):
        label = 'Mixed Accuracy - Partial Truths'
    else:
        label = 'Mixed Credibility'
    
    return {
        'score': round(score),
        'label': label,
        'verdict_counts': verdict_counts,
        'total_claims': len(fact_checks),
        'breakdown': {
            'verified_true': verified_true,
            'mostly_true': mostly_true,
            'verified_false': verified_false,
            'mostly_false': mostly_false,
            'misleading': misleading,
            'lacks_context': lacks_context,
            'partially_accurate': partially_accurate,
            'unverifiable': unverifiable,
            'opinion': verdict_counts.get('opinion', 0)
        }
    }

def generate_enhanced_conversational_summary(results: Dict) -> str:
    """Generate a comprehensive summary with insights"""
    
    cred_score = results.get('credibility_score', {})
    score = cred_score.get('score', 0)
    label = cred_score.get('label', 'Unknown')
    verdict_counts = cred_score.get('verdict_counts', {})
    total_claims = results.get('total_claims', 0)
    
    # Build summary
    summary_parts = []
    
    # Opening assessment
    summary_parts.append(f"📊 Fact-Check Analysis: {label}")
    summary_parts.append(f"Overall Accuracy Score: {score}%")
    summary_parts.append(f"Total Claims Analyzed: {total_claims}")
