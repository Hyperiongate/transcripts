"""
Main Flask Application for Political Fact Checker
Updated with enhanced verification system
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
    WOLFRAM_ALPHA_API_KEY = os.getenv('WOLFRAM_ALPHA_API_KEY')
    
    # Model config
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    
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
    # Use comprehensive fact checker instead of the basic enhanced one
    from services.comprehensive_factcheck import ComprehensiveFactChecker as FactChecker, VERDICT_CATEGORIES
    
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
            if job:
                job.pop('_id', None)
            return job
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
            job = get_job(job_id)
            if job:
                job.update(updates)
                redis_client.setex(f"job:{job_id}", 3600, json.dumps(job))
        else:
            if job_id in in_memory_jobs:
                in_memory_jobs[job_id].update(updates)
    except Exception as e:
        logger.error(f"Error updating job: {e}")
        if job_id in in_memory_jobs:
            in_memory_jobs[job_id].update(updates)

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start fact-checking analysis"""
    try:
        data = request.get_json()
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        if len(transcript) > 50000:
            return jsonify({'error': 'Transcript too long. Maximum 50,000 characters.'}), 400
        
        # Create job
        job_id = create_job(transcript)
        
        # Start processing in background
        thread = threading.Thread(target=process_transcript, args=(job_id, transcript))
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Analysis started'
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id: str):
    """Get job status"""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'status': job.get('status'),
        'progress': job.get('progress', 0),
        'message': job.get('message', ''),
        'error': job.get('error')
    })

@app.route('/api/results/<job_id>')
def get_results(job_id: str):
    """Get analysis results"""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.get('status') != 'completed':
        return jsonify({'error': 'Analysis not complete'}), 400
    
    return jsonify(job.get('results', {}))

@app.route('/api/export/<job_id>/<format>')
def export_results(job_id: str, format: str):
    """Export results in various formats"""
    if format not in ['json', 'txt', 'pdf']:
        return jsonify({'error': 'Invalid format'}), 400
    
    job = get_job(job_id)
    if not job or job.get('status') != 'completed':
        return jsonify({'error': 'Results not available'}), 404
    
    results = job.get('results', {})
    
    try:
        if format == 'json':
            return jsonify(results)
        
        elif format == 'txt':
            # Generate text report
            report = generate_text_report(results)
            return report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact_check_{job_id}.txt'
            }
        
        elif format == 'pdf':
            # TODO: Implement PDF export
            return jsonify({'error': 'PDF export not yet implemented'}), 501
            
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

# Processing functions
def process_transcript(job_id: str, transcript: str):
    """Process transcript in background"""
    try:
        # Update progress
        update_job(job_id, {
            'status': 'processing',
            'progress': 10,
            'message': 'Extracting claims...'
        })
        
        # Extract claims
        extraction_result = claim_extractor.extract(transcript)
        claims = extraction_result.get('claims', [])
        speakers = extraction_result.get('speakers', [])
        topics = extraction_result.get('topics', [])
        
        if not claims:
            update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'No verifiable claims found',
                'results': {
                    'claims': [],
                    'summary': 'No verifiable claims were found in the transcript.',
                    'credibility_score': None
                }
            })
            return
        
        # Update progress
        update_job(job_id, {
            'progress': 30,
            'message': f'Fact-checking {len(claims)} claims...'
        })
        
        # Fact check each claim
        fact_checks = []
        for i, claim in enumerate(claims):
            try:
                # Update progress
                progress = 30 + int((i / len(claims)) * 60)
                update_job(job_id, {
                    'progress': progress,
                    'message': f'Checking claim {i+1} of {len(claims)}...'
                })
                
                # Check claim
                result = fact_checker.check_claim_with_verdict(
                    claim.get('text', ''),
                    context={
                        'speaker': claim.get('speaker'),
                        'transcript': transcript
                    }
                )
                
                fact_checks.append({
                    'claim': claim.get('text', ''),
                    'speaker': claim.get('speaker', 'Unknown'),
                    'verdict': result.get('verdict'),
                    'explanation': result.get('explanation'),
                    'confidence': result.get('confidence'),
                    'sources': result.get('sources', [])
                })
                
            except Exception as e:
                logger.error(f"Error checking claim {i}: {e}")
                fact_checks.append({
                    'claim': claim.get('text', ''),
                    'speaker': claim.get('speaker', 'Unknown'),
                    'verdict': 'unverifiable',
                    'explanation': f'Error during verification: {str(e)}',
                    'confidence': 0,
                    'sources': []
                })
        
        # Calculate credibility score
        credibility_score = calculate_credibility_score(fact_checks)
        
        # Generate summary
        summary = generate_summary(fact_checks, credibility_score, speakers, topics)
        
        # Store results
        results = {
            'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
            'claims': fact_checks,
            'speakers': speakers,
            'topics': topics,
            'credibility_score': credibility_score,
            'summary': summary,
            'total_claims': len(claims),
            'extraction_method': extraction_result.get('extraction_method', 'unknown')
        }
        
        update_job(job_id, {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        logger.error(traceback.format_exc())
        update_job(job_id, {
            'status': 'failed',
            'error': str(e),
            'message': 'Analysis failed'
        })

def calculate_credibility_score(fact_checks: List[Dict]) -> Dict:
    """Calculate overall credibility score"""
    if not fact_checks:
        return {'score': 0, 'label': 'No claims'}
    
    # Count verdicts
    verdict_counts = {}
    total_score = 0
    scored_claims = 0
    
    for fc in fact_checks:
        verdict = fc.get('verdict', 'unverifiable')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        # Get score from verdict
        verdict_info = VERDICT_CATEGORIES.get(verdict, {})
        if verdict_info.get('score') is not None:
            total_score += verdict_info['score']
            scored_claims += 1
    
    # Calculate average score
    if scored_claims > 0:
        score = int(total_score / scored_claims)
    else:
        score = 50  # Default for unverifiable claims
    
    # Determine label
    if score >= 90:
        label = 'Highly Credible'
    elif score >= 70:
        label = 'Mostly Credible'
    elif score >= 50:
        label = 'Mixed Credibility'
    elif score >= 30:
        label = 'Low Credibility'
    else:
        label = 'Very Low Credibility'
    
    return {
        'score': score,
        'label': label,
        'verdict_breakdown': verdict_counts,
        'total_claims': len(fact_checks),
        'scored_claims': scored_claims
    }

def generate_summary(fact_checks: List[Dict], credibility_score: Dict, speakers: List[str], topics: List[str]) -> str:
    """Generate analysis summary"""
    total = len(fact_checks)
    score = credibility_score.get('score', 0)
    label = credibility_score.get('label', 'Unknown')
    
    # Count key verdicts
    verified_true = sum(1 for fc in fact_checks if fc.get('verdict') == 'verified_true')
    verified_false = sum(1 for fc in fact_checks if fc.get('verdict') == 'verified_false')
    partially_accurate = sum(1 for fc in fact_checks if fc.get('verdict') == 'partially_accurate')
    
    summary = f"Analysis of {total} claims reveals {label} ({score}/100).\n\n"
    
    if verified_true > 0:
        summary += f"✓ {verified_true} claims verified as true\n"
    if verified_false > 0:
        summary += f"✗ {verified_false} claims verified as false\n"
    if partially_accurate > 0:
        summary += f"⚠ {partially_accurate} claims partially accurate\n"
    
    if topics:
        summary += f"\nMain topics: {', '.join(topics)}"
    
    return summary

def generate_text_report(results: Dict) -> str:
    """Generate text format report"""
    report = []
    report.append("FACT CHECK REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Summary
    report.append("SUMMARY")
    report.append("-" * 20)
    report.append(results.get('summary', 'No summary available'))
    report.append("")
    
    # Credibility Score
    cred = results.get('credibility_score', {})
    report.append("CREDIBILITY SCORE")
    report.append("-" * 20)
    report.append(f"Score: {cred.get('score', 'N/A')}/100")
    report.append(f"Label: {cred.get('label', 'Unknown')}")
    report.append("")
    
    # Claims
    report.append("FACT CHECKS")
    report.append("-" * 20)
    
    for i, fc in enumerate(results.get('claims', []), 1):
        report.append(f"\n{i}. CLAIM: {fc.get('claim', 'Unknown')}")
        report.append(f"   Speaker: {fc.get('speaker', 'Unknown')}")
        report.append(f"   Verdict: {fc.get('verdict', 'Unknown').upper()}")
        report.append(f"   Explanation: {fc.get('explanation', 'No explanation')}")
        if fc.get('sources'):
            report.append(f"   Sources: {', '.join(fc['sources'])}")
    
    return "\n".join(report)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Main
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
