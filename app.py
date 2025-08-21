"""
Transcript Fact Checker - Main Flask Application
Enhanced version with improved verdict system and AI integration
"""
import os
import logging
import uuid
from datetime import datetime
from typing import List, Dict
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import json
from reportlab.lib import colors
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
    from services.factcheck import FactChecker, VERDICT_CATEGORIES
    
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

def calculate_credibility_score_enhanced(fact_checks: List[Dict]) -> Dict:
    """Calculate overall credibility score with nuanced verdicts"""
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
        verdict = fc.get('verdict', 'needs_context')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        # Get score for this verdict
        verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context'])
        if verdict_info['score'] is not None:
            total_score += verdict_info['score']
            scorable_claims += 1
    
    # Calculate weighted score
    if scorable_claims > 0:
        score = total_score / scorable_claims
    else:
        score = 50  # Default to middle if no scorable claims
    
    # Determine overall label
    if score >= 85:
        label = 'Highly Credible'
    elif score >= 70:
        label = 'Generally Credible'
    elif score >= 50:
        label = 'Mixed Credibility'
    elif score >= 30:
        label = 'Low Credibility'
    else:
        label = 'Very Low Credibility'
    
    # Check for deception patterns
    deceptive_count = verdict_counts.get('intentionally_deceptive', 0)
    false_count = verdict_counts.get('false', 0)
    misleading_count = verdict_counts.get('misleading', 0)
    
    if deceptive_count >= 3:
        label = 'Pattern of Deception Detected'
        score = max(score - 20, 0)  # Penalty for deception pattern
    elif false_count + misleading_count >= 5:
        label = 'Significant Credibility Issues'
        score = max(score - 10, 0)
    
    return {
        'score': round(score),
        'label': label,
        'verdict_counts': verdict_counts,
        'total_claims': len(fact_checks),
        'breakdown': {
            'accurate': verdict_counts.get('true', 0) + verdict_counts.get('mostly_true', 0) + verdict_counts.get('nearly_true', 0),
            'misleading': verdict_counts.get('exaggeration', 0) + verdict_counts.get('misleading', 0),
            'false': verdict_counts.get('mostly_false', 0) + verdict_counts.get('false', 0) + verdict_counts.get('intentionally_deceptive', 0),
            'other': verdict_counts.get('needs_context', 0) + verdict_counts.get('opinion', 0)
        }
    }

def generate_enhanced_conversational_summary(results: Dict) -> str:
    """Generate a more nuanced conversational summary with AI insights"""
    
    cred_score = results.get('credibility_score', {})
    score = cred_score.get('score', 0)
    label = cred_score.get('label', 'Unknown')
    verdict_counts = cred_score.get('verdict_counts', {})
    
    # Build detailed breakdown
    summary_parts = []
    
    # Opening assessment
    if score >= 85:
        summary_parts.append(f"✅ This transcript demonstrates {label} with a score of {score}%.")
        summary_parts.append("The vast majority of claims made were accurate and verifiable.")
    elif score >= 70:
        summary_parts.append(f"✓ This transcript shows {label} with a score of {score}%.")
        summary_parts.append("Most claims were accurate, though some minor issues were found.")
    elif score >= 50:
        summary_parts.append(f"⚠️ This transcript has {label} with a score of {score}%.")
        summary_parts.append("A mix of accurate and problematic claims were identified.")
    else:
        summary_parts.append(f"❌ This transcript shows {label} with a concerning score of only {score}%.")
        summary_parts.append("Significant accuracy issues were detected throughout.")
    
    # Detailed verdict breakdown
    summary_parts.append(f"\n📊 Detailed Analysis of {results.get('total_claims', 0)} claims:")
    
    # Group verdicts by category
    if verdict_counts:
        if verdict_counts.get('true', 0) > 0:
            summary_parts.append(f"• ✅ True: {verdict_counts['true']} claims")
        if verdict_counts.get('mostly_true', 0) > 0:
            summary_parts.append(f"• ✓ Mostly True: {verdict_counts['mostly_true']} claims")
        if verdict_counts.get('nearly_true', 0) > 0:
            summary_parts.append(f"• 🔵 Nearly True: {verdict_counts['nearly_true']} claims")
        if verdict_counts.get('exaggeration', 0) > 0:
            summary_parts.append(f"• 📏 Exaggerations: {verdict_counts['exaggeration']} claims")
        if verdict_counts.get('misleading', 0) > 0:
            summary_parts.append(f"• ⚠️ Misleading: {verdict_counts['misleading']} claims")
        if verdict_counts.get('mostly_false', 0) > 0:
            summary_parts.append(f"• ❌ Mostly False: {verdict_counts['mostly_false']} claims")
        if verdict_counts.get('false', 0) > 0:
            summary_parts.append(f"• ❌ False: {verdict_counts['false']} claims")
        if verdict_counts.get('intentionally_deceptive', 0) > 0:
            summary_parts.append(f"• 🚨 Intentionally Deceptive: {verdict_counts['intentionally_deceptive']} claims")
        if verdict_counts.get('opinion', 0) > 0:
            summary_parts.append(f"• 💭 Opinions: {verdict_counts['opinion']} statements")
        if verdict_counts.get('needs_context', 0) > 0:
            summary_parts.append(f"• ❓ Needs Context: {verdict_counts['needs_context']} claims")
    
    # Pattern detection
    deceptive_count = verdict_counts.get('intentionally_deceptive', 0)
    false_count = verdict_counts.get('false', 0)
    misleading_count = verdict_counts.get('misleading', 0)
    exaggeration_count = verdict_counts.get('exaggeration', 0)
    
    if deceptive_count >= 3:
        summary_parts.append("\n🚨 PATTERN DETECTED: Multiple instances of intentional deception indicate a deliberate attempt to mislead.")
    elif false_count >= 5:
        summary_parts.append("\n⚠️ PATTERN DETECTED: Numerous false claims suggest serious credibility issues.")
    elif misleading_count >= 4:
        summary_parts.append("\n⚠️ PATTERN DETECTED: Multiple misleading statements indicate a pattern of distortion.")
    elif exaggeration_count >= 5:
        summary_parts.append("\n📏 PATTERN DETECTED: Frequent exaggerations suggest a tendency to overstate facts.")
    
    # Speaker-specific insights
    speaker_context = results.get('speaker_context', {})
    if speaker_context:
        summary_parts.append("\n👤 Speaker Analysis:")
        for speaker, info in speaker_context.items():
            if info.get('false_claims_in_transcript', 0) > 0:
                summary_parts.append(f"• {speaker}: Made {info['false_claims_in_transcript']} false or misleading claims in this transcript")
            if info.get('warnings'):
                for warning in info['warnings']:
                    summary_parts.append(f"  ⚠️ {warning}")
    
    # Most problematic claims
    fact_checks = results.get('fact_checks', [])
    problematic_claims = [
        fc for fc in fact_checks 
        if fc.get('verdict') in ['false', 'mostly_false', 'intentionally_deceptive', 'misleading']
    ]
    
    if problematic_claims:
        summary_parts.append("\n❌ Most Concerning Claims:")
        for i, fc in enumerate(problematic_claims[:3], 1):
            claim_preview = fc['claim'][:100] + '...' if len(fc['claim']) > 100 else fc['claim']
            verdict_details = fc.get('verdict_details', {})
            verdict_label = verdict_details.get('label', fc['verdict'])
            summary_parts.append(f"{i}. \"{claim_preview}\" - Verdict: {verdict_label}")
    
    # Context about the event
    if 'debate' in results.get('source', '').lower():
        summary_parts.append("\n📅 Note: This analysis is from a political debate where fact-checking is especially important for informed voting.")
    
    # AI usage indication
    if Config.OPENAI_API_KEY:
        summary_parts.append("\n🤖 This analysis was enhanced with AI for improved accuracy and context understanding.")
    
    # Recommendation
    if score < 50:
        summary_parts.append("\n💡 Recommendation: Readers should verify claims independently due to the significant accuracy issues found.")
    elif score < 70:
        summary_parts.append("\n💡 Recommendation: While some claims are accurate, readers should approach with caution and verify key assertions.")
    
    return '\n'.join(summary_parts)

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
            # Count problematic claims by this speaker
            speaker_false_claims = 0
            speaker_misleading_claims = 0
            speaker_deceptive_claims = 0
            
            for fc in fact_checks:
                if fc.get('speaker', '').lower() == speaker_lower:
                    verdict = fc.get('verdict', '')
                    if verdict in ['false', 'mostly_false']:
                        speaker_false_claims += 1
                    elif verdict == 'misleading':
                        speaker_misleading_claims += 1
                    elif verdict == 'intentionally_deceptive':
                        speaker_deceptive_claims += 1
            
            total_problematic = speaker_false_claims + speaker_misleading_claims + speaker_deceptive_claims
            
            speaker_info[speaker] = {
                'full_name': matched_info.get('full_name', speaker),
                'role': matched_info.get('role', 'Unknown'),
                'party': matched_info.get('party', 'Unknown'),
                'credibility_notes': matched_info.get('credibility_notes', ''),
                'criminal_record': matched_info.get('criminal_record'),
                'fraud_history': matched_info.get('fraud_history'),
                'fact_check_history': matched_info.get('fact_check_history', ''),
                'false_claims_in_transcript': speaker_false_claims,
                'misleading_claims_in_transcript': speaker_misleading_claims,
                'deceptive_claims_in_transcript': speaker_deceptive_claims,
                'total_problematic_claims': total_problematic,
                'warnings': []
            }
            
            # Add warnings if applicable
            if matched_info.get('criminal_record'):
                speaker_info[speaker]['warnings'].append(f"Criminal Record: {matched_info['criminal_record']}")
            if matched_info.get('fraud_history'):
                speaker_info[speaker]['warnings'].append(f"Fraud History: {matched_info['fraud_history']}")
            if total_problematic >= 5:
                speaker_info[speaker]['warnings'].append(f"Made {total_problematic} false or misleading claims in this transcript")
    
    return speaker_info

def store_results(job_id: str, results: dict):
    """Store analysis results"""
    try:
        if results_collection:
            results_collection.insert_one({'_id': job_id, **results})
        else:
            in_memory_results[job_id] = results.copy()
            logger.info(f"Stored results for job {job_id} in memory")
        
        if redis_client:
            redis_client.setex(f"results:{job_id}", 86400, json.dumps(results))
    except Exception as e:
        logger.error(f"Error storing results: {e}")
        in_memory_results[job_id] = results.copy()

def get_results(job_id: str) -> dict:
    """Get analysis results"""
    try:
        # Try Redis first
        if redis_client:
            try:
                cached = redis_client.get(f"results:{job_id}")
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis get results failed: {e}")
        
        # Try MongoDB
        if results_collection:
            try:
                results = results_collection.find_one({'_id': job_id})
                if results:
                    results.pop('_id', None)
                    return results
            except Exception as e:
                logger.warning(f"MongoDB get results failed: {e}")
        
        # Fallback to memory
        return in_memory_results.get(job_id, {}).copy()
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return in_memory_results.get(job_id, {}).copy()

# Background task to process fact checking
def process_fact_check(job_id: str, transcript: str):
    """Process fact checking in background"""
    try:
        logger.info(f"Starting fact check for job {job_id}")
        update_job_progress(job_id, 10, "Extracting claims...")
        
        # Extract claims
        claims_data = claim_extractor.extract(transcript)
        if not claims_data:
            raise Exception("No claims could be extracted")
        
        claims = claims_data.get('claims', [])
        speakers = claims_data.get('speakers', [])
        topics = claims_data.get('topics', [])
        
        logger.info(f"Extracted {len(claims)} claims from {len(speakers)} speakers")
        update_job_progress(job_id, 30, f"Checking {len(claims)} claims...")
        
        # Fact check each claim
        fact_checks = []
        for i, claim in enumerate(claims):
            try:
                # Update progress
                progress = 30 + int((i / len(claims)) * 60)
                update_job_progress(job_id, progress, f"Checking claim {i+1} of {len(claims)}...")
                
                # Fact check with enhanced verdict system
                result = fact_checker.check_claim_with_verdict(claim['text'])
                result['speaker'] = claim.get('speaker', 'Unknown')
                result['claim'] = claim['text']
                result['context'] = claim.get('context', '')
                fact_checks.append(result)
                
            except Exception as e:
                logger.error(f"Error checking claim {i}: {e}")
                fact_checks.append({
                    'claim': claim['text'],
                    'verdict': 'error',
                    'explanation': f"Error checking claim: {str(e)}",
                    'sources': [],
                    'speaker': claim.get('speaker', 'Unknown')
                })
        
        # Calculate credibility score
        update_job_progress(job_id, 90, "Calculating credibility score...")
        credibility_score = calculate_credibility_score_enhanced(fact_checks)
        
        # Analyze speaker credibility
        speaker_context = analyze_speaker_credibility(speakers, fact_checks)
        
        # Prepare results
        results = {
            'job_id': job_id,
            'total_claims': len(claims),
            'checked_claims': len(fact_checks),
            'fact_checks': fact_checks,
            'credibility_score': credibility_score,
            'speakers': speakers,
            'topics': topics,
            'speaker_context': speaker_context,
            'source': 'transcript',
            'completed_at': datetime.utcnow().isoformat()
        }
        
        # Generate enhanced conversational summary
        results['conversational_summary'] = generate_enhanced_conversational_summary(results)
        
        # Store results
        store_results(job_id, results)
        
        # Update job status
        update_job(job_id, {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'completed_at': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Completed fact check for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error in fact check process: {e}")
        logger.error(traceback.format_exc())
        update_job(job_id, {
            'status': 'failed',
            'progress': -1,
            'message': f"Error: {str(e)}",
            'error': str(e)
        })

# Routes
@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'mongodb': 'connected' if mongo_client else 'not connected',
        'redis': 'connected' if redis_client else 'not connected',
        'services': {
            'transcript_processor': 'ready',
            'claim_extractor': 'ready',
            'fact_checker': 'ready'
        }
    })

@app.route('/api/submit', methods=['POST'])
def submit_transcript():
    """Submit transcript for fact checking"""
    try:
        data = request.get_json()
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({'error': f'Transcript too long. Maximum {Config.MAX_TRANSCRIPT_LENGTH} characters allowed.'}), 400
        
        # Clean transcript
        transcript = transcript_processor.clean_transcript(transcript)
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            'status': 'queued',
            'progress': 0,
            'message': 'Processing started',
            'created_at': datetime.utcnow().isoformat(),
            'transcript_length': len(transcript)
        }
        
        # Store job
        store_job(job_id, job_data)
        
        # Start background processing
        thread = Thread(target=process_fact_check, args=(job_id, transcript))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'processing'
        })
        
    except Exception as e:
        logger.error(f"Error in submit_transcript: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def check_status(job_id):
    """Check job status"""
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job)
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<job_id>')
def get_fact_check_results(job_id):
    """Get fact check results"""
    try:
        # Check job status first
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job['status'] != 'completed':
            return jsonify({
                'error': 'Job not completed',
                'status': job['status'],
                'progress': job.get('progress', 0)
            }), 202
        
        # Get results
        results = get_results(job_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<job_id>', methods=['GET'])
def export_results(job_id):
    """Export results as PDF"""
    try:
        # Get results
        results = get_results(job_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Title
        story.append(Paragraph("Transcript Fact Check Report", title_style))
        story.append(Spacer(1, 0.5*inch))
        
        # Summary
        summary_style = ParagraphStyle(
            'Summary',
            parent=styles['Normal'],
            fontSize=12,
            leading=16,
            spaceAfter=20
        )
        
        if results.get('conversational_summary'):
            summary_text = results['conversational_summary'].replace('\n', '<br/>')
            story.append(Paragraph("<b>Executive Summary</b>", styles['Heading2']))
            story.append(Paragraph(summary_text, summary_style))
            story.append(Spacer(1, 0.3*inch))
        
        # Credibility Score
        cred_score = results.get('credibility_score', {})
        story.append(Paragraph(f"<b>Overall Credibility Score: {cred_score.get('score', 0)}%</b>", styles['Heading2']))
        story.append(Paragraph(f"Rating: {cred_score.get('label', 'Unknown')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Fact Checks Table
        story.append(Paragraph("<b>Detailed Fact Checks</b>", styles['Heading2']))
        story.append(Spacer(1, 0.2*inch))
        
        # Create table data
        table_data = [['Claim', 'Verdict', 'Explanation']]
        
        for fc in results.get('fact_checks', []):
            claim_text = fc.get('claim', '')[:100] + '...' if len(fc.get('claim', '')) > 100 else fc.get('claim', '')
            verdict = fc.get('verdict', 'Unknown').replace('_', ' ').title()
            explanation = fc.get('explanation', '')[:150] + '...' if len(fc.get('explanation', '')) > 150 else fc.get('explanation', '')
            
            table_data.append([
                Paragraph(claim_text, styles['Normal']),
                Paragraph(verdict, styles['Normal']),
                Paragraph(explanation, styles['Normal'])
            ])
        
        # Create table
        table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'fact_check_report_{job_id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Validate configuration on startup
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)
