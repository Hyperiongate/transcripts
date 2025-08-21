"""
Transcript Fact Checker - Main Flask Application
Optimized version with parallel processing
"""
import os
import logging
import uuid
from datetime import datetime
from typing import List, Dict
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
import io
from threading import Thread
import time
import traceback

# Load environment variables first
load_dotenv()

# Import configuration
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Database initialization with fallback
mongo_client = None
db = None
jobs_collection = None
results_collection = None
redis_client = None

# In-memory storage as fallback
in_memory_jobs = {}
in_memory_results = {}

# Try to connect to MongoDB if configured
if Config.MONGODB_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        mongo_client.server_info()
        db = mongo_client[Config.MONGODB_DB_NAME]
        jobs_collection = db['jobs']
        results_collection = db['results']
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
    from services.factcheck import FactChecker
    
    # Initialize services
    transcript_processor = TranscriptProcessor()
    claim_extractor = ClaimExtractor(openai_api_key=Config.OPENAI_API_KEY)
    fact_checker = FactChecker(Config)
    logger.info("Services initialized successfully")
except ImportError as e:
    logger.error(f"CRITICAL: Failed to import required services: {str(e)}")
    logger.error("Please ensure services directory exists with transcript.py, claims.py, and factcheck.py")
    raise SystemExit(f"Cannot start application without services: {str(e)}")

# Enhanced speaker database
SPEAKER_DATABASE = {
    'donald trump': {
        'full_name': 'Donald J. Trump',
        'role': '45th and 47th President of the United States',
        'party': 'Republican',
        'criminal_record': 'Multiple indictments in 2023-2024',
        'fraud_history': 'Trump Organization fraud conviction 2022',
        'fact_check_history': 'Extensive record of false and misleading statements',
        'credibility_notes': 'Known for frequent false claims and exaggerations'
    },
    'j.d. vance': {
        'full_name': 'James David Vance',
        'role': 'Vice President of the United States',
        'party': 'Republican',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Mixed record on factual accuracy',
        'credibility_notes': 'Serving as VP since January 2025'
    },
    'joe biden': {
        'full_name': 'Joseph R. Biden Jr.',
        'role': '46th President of the United States (2021-2025)',
        'party': 'Democrat',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Generally accurate with occasional misstatements',
        'credibility_notes': 'Former President'
    },
    'kamala harris': {
        'full_name': 'Kamala D. Harris',
        'role': 'Former Vice President of the United States (2021-2025)',
        'party': 'Democrat',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Generally accurate',
        'credibility_notes': 'Former Vice President'
    }
}

# Helper functions
def store_job(job_id: str, job_data: dict):
    """Store job in database or memory"""
    try:
        if jobs_collection:
            jobs_collection.insert_one({'_id': job_id, **job_data})
        else:
            in_memory_jobs[job_id] = job_data.copy()
            logger.info(f"Stored job {job_id} in memory with status: {job_data.get('status')}")
        
        if redis_client:
            redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
    except Exception as e:
        logger.error(f"Error storing job: {e}")
        in_memory_jobs[job_id] = job_data.copy()

def get_job(job_id: str) -> dict:
    """Get job from database or memory"""
    try:
        # Try Redis first for speed
        if redis_client:
            try:
                cached = redis_client.get(f"job:{job_id}")
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Try MongoDB
        if jobs_collection:
            try:
                job = jobs_collection.find_one({'_id': job_id})
                if job:
                    job.pop('_id', None)
                    return job
            except Exception as e:
                logger.warning(f"MongoDB get failed: {e}")
        
        # Fallback to memory
        job = in_memory_jobs.get(job_id)
        if job:
            logger.info(f"Retrieved job {job_id} from memory with status: {job.get('status')}")
            return job.copy()
        
        logger.warning(f"Job {job_id} not found in any storage")
        return None
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        return in_memory_jobs.get(job_id, {}).copy() if job_id in in_memory_jobs else None

def update_job(job_id: str, updates: dict):
    """Update job in database or memory"""
    try:
        if jobs_collection:
            try:
                jobs_collection.update_one(
                    {'_id': job_id},
                    {'$set': updates}
                )
            except Exception as e:
                logger.warning(f"MongoDB update failed: {e}")
                if job_id in in_memory_jobs:
                    in_memory_jobs[job_id].update(updates)
        else:
            if job_id in in_memory_jobs:
                in_memory_jobs[job_id].update(updates)
                logger.info(f"Updated job {job_id} in memory with: {list(updates.keys())}")
            else:
                logger.error(f"Job {job_id} not found in memory for update")
        
        # Update cache if exists
        if redis_client:
            try:
                job_data = get_job(job_id)
                if job_data:
                    redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
            except Exception as e:
                logger.warning(f"Redis update failed: {e}")
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

def generate_conversational_summary(results: Dict) -> str:
    """Generate a conversational summary of the fact check results"""
    cred_score = results.get('credibility_score', {})
    score = cred_score.get('score', 0)
    label = cred_score.get('label', 'Unknown')
    true_claims = cred_score.get('true_claims', 0)
    false_claims = cred_score.get('false_claims', 0)
    mixed_claims = cred_score.get('mixed_claims', 0)
    unverified_claims = cred_score.get('unverified_claims', 0)
    total_claims = results.get('total_claims', 0)
    
    # Start with overall assessment
    if score >= 80:
        summary = f"Overall, this transcript shows {label} with a score of {score}%. "
        summary += f"Most claims ({true_claims} out of {total_claims}) were verified as accurate. "
    elif score >= 60:
        summary = f"This transcript has {label} with a score of {score}%. "
        summary += f"While {true_claims} claims were true, there were also {false_claims} false claims and {mixed_claims} misleading statements. "
    elif score >= 40:
        summary = f"This transcript demonstrates {label} with a concerning score of {score}%. "
        summary += f"Out of {total_claims} claims analyzed, {false_claims} were false and {mixed_claims} were misleading. "
    else:
        summary = f"⚠️ This transcript has {label} with a score of only {score}%. "
        summary += f"This is concerning: {false_claims} false claims and {mixed_claims} misleading statements out of {total_claims} total claims. "
    
    # Add pattern detection
    if false_claims >= 5:
        summary += f"\n\n🚨 PATTERN DETECTED: With {false_claims} false claims, this indicates a pattern of misinformation. "
    elif false_claims >= 3:
        summary += f"\n\n⚠️ WARNING: Multiple false claims ({false_claims}) suggest credibility issues. "
    
    # Add speaker-specific warnings
    speaker_context = results.get('speaker_context', {})
    for speaker, info in speaker_context.items():
        if info.get('warnings'):
            summary += f"\n\n📋 {speaker}: "
            summary += " ".join(info['warnings'])
    
    # Highlight most problematic claims
    fact_checks = results.get('fact_checks', [])
    false_claim_examples = [fc for fc in fact_checks if fc.get('verdict', '').lower() in ['false', 'mostly_false']]
    
    if false_claim_examples:
        summary += "\n\n❌ Most concerning false claims:"
        for i, fc in enumerate(false_claim_examples[:3], 1):
            summary += f"\n{i}. \"{fc['claim'][:100]}...\" - {fc.get('explanation', '')[:150]}"
    
    # Add context about the event if it's a debate
    if 'debate' in results.get('source', '').lower():
        summary += "\n\n📅 Context: This appears to be from a political debate where fact-checking is especially important for voters."
    
    return summary

def calculate_credibility_score(fact_checks: List[Dict]) -> Dict:
    """Calculate overall credibility score"""
    if not fact_checks:
        return {
            'score': 0,
            'label': 'No claims verified',
            'true_claims': 0,
            'false_claims': 0,
            'mixed_claims': 0,
            'unverified_claims': 0
        }
    
    # Count verdicts
    true_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['true', 'mostly true', 'correct', 'accurate'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['false', 'mostly false', 'incorrect', 'inaccurate'])
    mixed_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['mixed', 'partially true', 'half true', 'misleading'])
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['unverified', 'unsubstantiated', 'lacks_context', 'needs_context'])
    
    total = len(fact_checks)
    
    # Calculate weighted score
    score = ((true_count * 100) + (mixed_count * 50) + (unverified_count * 30)) / total if total > 0 else 0
    
    # Determine label
    if score >= 80:
        label = 'High Credibility'
    elif score >= 60:
        label = 'Moderate Credibility'
    elif score >= 40:
        label = 'Low Credibility'
    else:
        label = 'Very Low Credibility'
    
    return {
        'score': round(score),
        'label': label,
        'true_claims': true_count,
        'false_claims': false_count,
        'mixed_claims': mixed_count,
        'unverified_claims': unverified_count
    }

def analyze_speaker_credibility(speakers: List[str], fact_checks: List[Dict]) -> Dict:
    """Analyze speaker credibility with comprehensive background"""
    speaker_info = {}
    
    # Process each speaker
    for speaker in speakers:
        if not speaker:
            continue
            
        speaker_lower = speaker.lower()
        matched_info = None
        
        # Find matching speaker in database
        for key, info in SPEAKER_DATABASE.items():
            if key in speaker_lower or speaker_lower in key:
                matched_info = info
                break
        
        if matched_info:
            # Count false claims by this speaker
            speaker_false_claims = sum(1 for fc in fact_checks 
                                     if fc.get('speaker', '').lower() == speaker_lower 
                                     and fc.get('verdict', '').lower() in ['false', 'mostly_false'])
            
            speaker_info[speaker] = {
                'full_name': matched_info.get('full_name', speaker),
                'role': matched_info.get('role', 'Unknown'),
                'party': matched_info.get('party', 'Unknown'),
                'credibility_notes': matched_info.get('credibility_notes', ''),
                'historical_accuracy': matched_info.get('fact_check_history', 'No data available'),
                'false_claims_in_transcript': speaker_false_claims
            }
            
            # Add warnings
            warnings = []
            if matched_info.get('criminal_record'):
                warnings.append(f"Criminal Record: {matched_info['criminal_record']}")
            if matched_info.get('fraud_history'):
                warnings.append(f"Fraud History: {matched_info['fraud_history']}")
            if speaker_false_claims >= 3:
                warnings.append(f"Made {speaker_false_claims} false claims in this transcript")
            
            if warnings:
                speaker_info[speaker]['warnings'] = warnings
                
            # Add pattern detection
            if speaker_false_claims >= 5:
                speaker_info[speaker]['pattern_detected'] = f"Pattern of deception: {speaker_false_claims} false claims"
    
    return speaker_info

# Routes
@app.route('/')
def index():
    """Render main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return jsonify({'error': 'Failed to load page'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    db_status = "connected" if mongo_client else "in-memory"
    redis_status = "connected" if redis_client else "in-memory"
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'storage': {
            'database': db_status,
            'cache': redis_status
        },
        'services': 'available'
    })

@app.route('/api/test', methods=['GET', 'POST'])
def test_api():
    """Test endpoint to verify API is working"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'message': 'API is working',
            'method': 'GET'
        })
    else:
        # POST test
        try:
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': 'POST received',
                'received_data': data,
                'content_type': request.content_type
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'content_type': request.content_type,
                'data': request.data.decode('utf-8')[:200]
            })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Analyze transcript endpoint - ENHANCED DEBUG VERSION"""
    try:
        # Log incoming request details
        logger.info(f"Received POST to /api/analyze")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Request data length: {len(request.data)}")
        
        # Check if request has JSON content type
        if request.content_type and 'application/json' not in request.content_type:
            logger.error(f"Invalid Content-Type: {request.content_type}")
            return jsonify({
                'success': False, 
                'error': f'Invalid Content-Type: {request.content_type}. Expected application/json'
            }), 400
        
        # Try to parse JSON data
        try:
            data = request.get_json(force=True)  # Force parsing even if content-type is wrong
            logger.info(f"Parsed JSON data keys: {list(data.keys()) if data else 'None'}")
        except Exception as json_error:
            logger.error(f"JSON parsing error: {str(json_error)}")
            logger.error(f"Raw data: {request.data[:200]}")
            return jsonify({
                'success': False, 
                'error': f'Invalid JSON data: {str(json_error)}'
            }), 400
        
        if not data:
            logger.error("No JSON data in request body")
            return jsonify({
                'success': False, 
                'error': 'No data provided. Please send JSON with transcript and source fields'
            }), 400
        
        # Validate input
        transcript = data.get('transcript', '').strip()
        source = data.get('source', 'Direct Input')
        
        logger.info(f"Transcript length: {len(transcript)}")
        logger.info(f"Source: {source}")
        
        if not transcript:
            logger.error("No transcript in request data")
            return jsonify({'success': False, 'error': 'No transcript provided'}), 400
        
        if len(transcript) < 50:
            logger.error(f"Transcript too short: {len(transcript)} characters")
            return jsonify({
                'success': False, 
                'error': f'Transcript too short ({len(transcript)} characters). Minimum 50 characters required.'
            }), 400
        
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            logger.error(f"Transcript too long: {len(transcript)} characters")
            return jsonify({
                'success': False, 
                'error': f'Transcript too long (maximum {Config.MAX_TRANSCRIPT_LENGTH} characters)'
            }), 400
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            'status': 'processing',
            'progress': 0,
            'message': 'Initializing...',
            'source': source,
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"Created job {job_id}")
        
        # Store job
        store_job(job_id, job_data)
        
        # Process transcript in background thread to avoid blocking
        thread = Thread(target=process_transcript_async, args=(job_id, transcript, source))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started processing thread for job {job_id}")
        
        return jsonify({'success': True, 'job_id': job_id})
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

def process_transcript_async(job_id: str, transcript: str, source: str):
    """Process transcript asynchronously with optimizations"""
    try:
        # Step 1: Process transcript (10% - faster)
        update_job_progress(job_id, 10, 'Processing transcript...')
        processed_transcript = transcript_processor.process(transcript)
        
        # Step 2: Extract metadata (15% - quick)
        update_job_progress(job_id, 15, 'Extracting metadata...')
        metadata = transcript_processor.extract_metadata(processed_transcript)
        
        # Step 3: Extract claims (25% - optimized)
        update_job_progress(job_id, 25, 'Extracting claims...')
        claims_data = claim_extractor.extract_claims(
            processed_transcript, 
            max_claims=min(Config.MAX_CLAIMS_PER_TRANSCRIPT, 20)
        )
        
        # Extract just the claim text for fact checking
        if not claims_data:
            update_job_progress(job_id, 100, 'No verifiable claims found')
            update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'Analysis complete - no verifiable claims found',
                'fact_checks': [],
                'credibility_score': calculate_credibility_score([]),
                'metadata': metadata,
                'source': source,
                'total_claims': 0,
                'speakers': [],
                'topics': [],
                'speaker_context': {},
                'conversational_summary': 'No verifiable claims were found in this transcript.',
                'completed_at': datetime.now().isoformat()
            })
            return
        
        claims = claims_data if isinstance(claims_data[0], str) else [c['text'] for c in claims_data]
        
        logger.info(f"Job {job_id}: Found {len(claims)} claims to verify")
        
        # Step 4: Fact check claims (30-90% - PARALLEL PROCESSING)
        update_job_progress(job_id, 30, f'Fact-checking {len(claims)} claims...')
        
        # Process claims in batches with progress updates
        fact_checks = []
        batch_size = 5
        
        for i in range(0, len(claims), batch_size):
            batch = claims[i:i+batch_size]
            progress = 30 + int((i / len(claims)) * 60)
            
            update_job_progress(
                job_id, 
                progress, 
                f'Checking claims {i+1}-{min(i+batch_size, len(claims))} of {len(claims)}...'
            )
            
            # Check batch in parallel
            batch_results = fact_checker.check_claims(batch, source=source)
            fact_checks.extend(batch_results)
            
            # Small delay to prevent overwhelming APIs
            time.sleep(0.1)
        
        # Step 5: Calculate final scores (90%)
        update_job_progress(job_id, 90, 'Calculating credibility score...')
        
        # Add claim context for better display
        for i, fc in enumerate(fact_checks):
            if i < len(claims_data) and isinstance(claims_data[i], dict):
                fc['indicators'] = claims_data[i].get('indicators', [])
                fc['confidence_score'] = claims_data[i].get('confidence', 
                                                           claims_data[i].get('score', 0))
        
        credibility_score = calculate_credibility_score(fact_checks)
        
        # Extract speaker context if available
        try:
            speakers, topics = claim_extractor.extract_context(transcript)
        except Exception as e:
            logger.warning(f"Failed to extract context: {e}")
            speakers, topics = [], []
        
        speaker_context = analyze_speaker_credibility(speakers, fact_checks)
        
        # Generate conversational summary
        conversational_summary = generate_conversational_summary({
            'credibility_score': credibility_score,
            'total_claims': len(claims),
            'fact_checks': fact_checks,
            'speaker_context': speaker_context,
            'source': source
        })
        
        # Complete (100%)
        update_job_progress(job_id, 100, 'Analysis complete')
        
        # Get creation time safely
        job_creation = get_job(job_id)
        if job_creation and 'created_at' in job_creation:
            processing_time = (datetime.now() - datetime.fromisoformat(
                job_creation['created_at'])).total_seconds()
        else:
            processing_time = 0
        
        # Final results
        results = {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'fact_checks': fact_checks,
            'credibility_score': credibility_score,
            'total_claims': len(claims),
            'processing_time': processing_time,
            'speakers': speakers,
            'topics': topics,
            'source': source,
            'metadata': metadata,
            'speaker_context': speaker_context,
            'conversational_summary': conversational_summary,
            'completed_at': datetime.now().isoformat()
        }
        
        # Log what we're storing
        logger.info(f"Storing final results for job {job_id}:")
        logger.info(f"  - Status: {results['status']}")
        logger.info(f"  - Total claims: {results['total_claims']}")
        logger.info(f"  - Credibility score: {results['credibility_score']}")
        logger.info(f"  - Fact checks count: {len(results['fact_checks'])}")
        
        # Store results
        update_job(job_id, results)
        
        # Verify storage
        stored_job = get_job(job_id)
        if stored_job:
            logger.info(f"Verified job {job_id} stored with status: {stored_job.get('status')}")
        else:
            logger.error(f"Failed to verify storage of job {job_id}")
        
    except Exception as e:
        logger.error(f"Processing error in job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        update_job_progress(job_id, -1, f'Error: {str(e)}')
        update_job(job_id, {'status': 'failed', 'error': str(e)})

@app.route('/api/status/<job_id>')
def check_status(job_id):
    """Check job status"""
    try:
        job = get_job(job_id)
        
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # If job is completed, return full details including credibility score
        if job.get('status') == 'completed':
            # Extract credibility score details for completed jobs
            cred_score = job.get('credibility_score', {})
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': job.get('status'),
                'progress': job.get('progress', 100),
                'message': job.get('message', 'Analysis complete'),
                'credibility_score': cred_score.get('score', 0),
                'credibility_label': cred_score.get('label', 'Unknown'),
                'total_claims': job.get('total_claims', 0),
                'true_claims': cred_score.get('true_claims', 0),
                'false_claims': cred_score.get('false_claims', 0),
                'unverified_claims': cred_score.get('unverified_claims', 0),
                'mixed_claims': cred_score.get('mixed_claims', 0),
                'error': job.get('error')
            })
        else:
            # For processing jobs, return minimal info
            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': job.get('status'),
                'progress': job.get('progress', 0),
                'message': job.get('message', ''),
                'error': job.get('error')
            })
            
    except Exception as e:
        logger.error(f"Status check error for job {job_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    try:
        results = get_job(job_id)
        if not results:
            return jsonify({'success': False, 'error': 'Results not found'}), 404
        
        if results.get('status') != 'completed':
            return jsonify({
                'success': False, 
                'error': 'Analysis not completed',
                'status': results.get('status', 'unknown')
            }), 400
        
        # Extract credibility score details
        cred_score = results.get('credibility_score', {})
        
        # Format the response for the frontend
        response_data = {
            'success': True,
            'job_id': job_id,
            'credibility_score': cred_score.get('score', 0),
            'credibility_label': cred_score.get('label', 'Unknown'),
            'total_claims': results.get('total_claims', 0),
            'true_claims': cred_score.get('true_claims', 0),
            'false_claims': cred_score.get('false_claims', 0),
            'unverified_claims': cred_score.get('unverified_claims', 0),
            'mixed_claims': cred_score.get('mixed_claims', 0),
            'fact_checks': results.get('fact_checks', []),
            'metadata': results.get('metadata', {}),
            'speakers': results.get('speakers', []),
            'topics': results.get('topics', []),
            'speaker_context': results.get('speaker_context', {}),
            'conversational_summary': results.get('conversational_summary', ''),
            'source': results.get('source', 'Unknown'),
            'processing_time': results.get('processing_time', 0),
            'completed_at': results.get('completed_at', ''),
            'status': results.get('status', 'completed'),
            'message': results.get('message', 'Analysis complete')
        }
        
        # Log for debugging
        logger.info(f"Returning results for job {job_id}: credibility_score={response_data['credibility_score']}, total_claims={response_data['total_claims']}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Results retrieval error for job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/<job_id>/<format>')
def export_results(job_id, format):
    """Export results in different formats"""
    try:
        job = get_job(job_id)
        
        if not job or job.get('status') != 'completed':
            return jsonify({'error': 'Results not available'}), 404
        
        if format == 'json':
            # JSON export
            return jsonify({
                'transcript_source': job.get('source', 'Unknown'),
                'analysis_date': job.get('completed_at', datetime.now().isoformat()),
                'credibility_score': job.get('credibility_score', {}),
                'fact_checks': job.get('fact_checks', []),
                'metadata': job.get('metadata', {}),
                'processing_time': job.get('processing_time', 0),
                'conversational_summary': job.get('conversational_summary', ''),
                'speaker_context': job.get('speaker_context', {})
            })
            
        elif format == 'txt':
            # Text export
            output = []
            output.append("TRANSCRIPT FACT CHECK REPORT")
            output.append("=" * 50)
            output.append(f"Date: {job.get('completed_at', datetime.now().isoformat())}")
            output.append(f"Source: {job.get('source', 'Unknown')}")
            output.append(f"Processing Time: {job.get('processing_time', 0):.1f} seconds")
            output.append("")
            
            # Conversational Summary
            output.append("ANALYSIS SUMMARY:")
            output.append("-" * 50)
            output.append(job.get('conversational_summary', 'No summary available'))
            output.append("")
            
            # Credibility Score
            score = job.get('credibility_score', {})
            output.append(f"OVERALL CREDIBILITY: {score.get('label', 'Unknown')} ({score.get('score', 0)}%)")
            output.append(f"True Claims: {score.get('true_claims', 0)}")
            output.append(f"False Claims: {score.get('false_claims', 0)}")
            output.append(f"Mixed Claims: {score.get('mixed_claims', 0)}")
            output.append(f"Unverified: {score.get('unverified_claims', 0)}")
            output.append("")
            
            # Fact Checks
            output.append("FACT CHECK DETAILS:")
            output.append("-" * 50)
            
            for i, fc in enumerate(job.get('fact_checks', []), 1):
                output.append(f"\n{i}. CLAIM: {fc.get('claim', 'N/A')}")
                output.append(f"   VERDICT: {fc.get('verdict', 'Unknown').upper()}")
                if fc.get('explanation'):
                    output.append(f"   EXPLANATION: {fc.get('explanation')}")
                if fc.get('sources'):
                    output.append(f"   SOURCES: {', '.join(fc.get('sources', []))}")
            
            response = io.BytesIO()
            response.write('\n'.join(output).encode('utf-8'))
            response.seek(0)
            
            return send_file(
                response,
                mimetype='text/plain',
                as_attachment=True,
                download_name=f'fact_check_report_{job_id}.txt'
            )
            
        elif format == 'pdf':
            # PDF export
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a73e8'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph("Transcript Fact Check Report", title_style))
            story.append(Spacer(1, 20))
            
            # Metadata
            info_style = styles['Normal']
            story.append(Paragraph(f"<b>Date:</b> {job.get('completed_at', 'N/A')}", info_style))
            story.append(Paragraph(f"<b>Source:</b> {job.get('source', 'Unknown')}", info_style))
            story.append(Paragraph(f"<b>Processing Time:</b> {job.get('processing_time', 0):.1f} seconds", info_style))
            story.append(Spacer(1, 20))
            
            # Conversational Summary
            summary_style = ParagraphStyle(
                'SummaryStyle',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=20,
                leftIndent=20,
                rightIndent=20
            )
            story.append(Paragraph("<b>Analysis Summary:</b>", styles['Heading2']))
            summary_text = job.get('conversational_summary', 'No summary available').replace('\n', '<br/>')
            story.append(Paragraph(summary_text, summary_style))
            story.append(Spacer(1, 20))
            
            # Credibility Score
            score = job.get('credibility_score', {})
            score_style = ParagraphStyle(
                'ScoreStyle',
                parent=styles['Heading2'],
                fontSize=18,
                textColor=colors.HexColor('#34a853'),
                spaceAfter=10
            )
            story.append(Paragraph(f"Overall Credibility: {score.get('label', 'Unknown')} ({score.get('score', 0)}%)", score_style))
            
            # Score table
            score_data = [
                ['Metric', 'Count'],
                ['True Claims', str(score.get('true_claims', 0))],
                ['False Claims', str(score.get('false_claims', 0))],
                ['Mixed Claims', str(score.get('mixed_claims', 0))],
                ['Unverified Claims', str(score.get('unverified_claims', 0))]
            ]
            
            score_table = Table(score_data, colWidths=[200, 100])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(score_table)
            story.append(Spacer(1, 30))
            
            # Fact Checks
            story.append(Paragraph("Fact Check Details", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            for i, fc in enumerate(job.get('fact_checks', []), 1):
                claim_style = ParagraphStyle(
                    'ClaimStyle',
                    parent=styles['Normal'],
                    fontSize=11,
                    leftIndent=20,
                    rightIndent=20,
                    spaceAfter=5
                )
                
                # Determine color based on verdict
                verdict = fc.get('verdict', 'unknown').lower()
                if verdict in ['true', 'correct', 'accurate', 'mostly true']:
                    verdict_color = '#34a853'
                elif verdict in ['false', 'incorrect', 'inaccurate', 'mostly false']:
                    verdict_color = '#ea4335'
                elif verdict in ['mixed', 'partially true', 'half true']:
                    verdict_color = '#ff9800'
                else:
                    verdict_color = '#fbbc04'
                
                # Escape HTML in claim text
                claim_text = str(fc.get('claim', 'N/A')).replace('<', '&lt;').replace('>', '&gt;')
                explanation_text = str(fc.get('explanation', '')).replace('<', '&lt;').replace('>', '&gt;')
                
                story.append(Paragraph(f"<b>{i}. Claim:</b> {claim_text}", claim_style))
                story.append(Paragraph(f"<b>Verdict:</b> <font color='{verdict_color}'>{fc.get('verdict', 'Unknown').upper()}</font>", claim_style))
                
                if explanation_text:
                    story.append(Paragraph(f"<b>Explanation:</b> {explanation_text}", claim_style))
                
                if fc.get('sources'):
                    sources_text = ', '.join(str(s) for s in fc.get('sources', []))
                    story.append(Paragraph(f"<b>Sources:</b> {sources_text}", claim_style))
                
                story.append(Spacer(1, 15))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'fact_check_report_{job_id}.pdf'
            )
        else:
            return jsonify({'error': 'Invalid format. Use json, txt, or pdf'}), 400
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Export failed', 'details': str(e)}), 500

@app.route('/api/export/<job_id>/pdf')
def export_pdf(job_id):
    """Direct PDF export endpoint for backward compatibility"""
    return export_results(job_id, 'pdf')

@app.route('/api/debug/jobs')
def debug_jobs():
    """Debug endpoint to see all jobs in memory"""
    if not Config.DEBUG:
        return jsonify({'error': 'Debug mode not enabled'}), 403
    
    jobs_summary = {}
    for job_id, job_data in in_memory_jobs.items():
        jobs_summary[job_id] = {
            'status': job_data.get('status'),
            'progress': job_data.get('progress'),
            'created_at': job_data.get('created_at'),
            'completed_at': job_data.get('completed_at'),
            'has_credibility_score': 'credibility_score' in job_data,
            'has_fact_checks': 'fact_checks' in job_data and len(job_data.get('fact_checks', [])) > 0,
            'total_claims': job_data.get('total_claims', 0)
        }
    
    return jsonify({
        'total_jobs': len(in_memory_jobs),
        'jobs': jobs_summary,
        'storage_type': 'in-memory'
    })

@app.route('/api/debug/job/<job_id>')
def debug_job_details(job_id):
    """Debug endpoint to see specific job details"""
    if not Config.DEBUG:
        return jsonify({'error': 'Debug mode not enabled'}), 403
    
    job = in_memory_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'job_id': job_id,
        'full_data': job
    })

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Validate configuration on startup
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    # Use environment variable PORT if available (for Render)
    port = int(os.environ.get('PORT', Config.PORT))
    
    # Run the app
    logger.info(f"Starting app on port {port}")
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=port)
