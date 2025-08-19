"""
Transcript Fact Checker - Main Flask Application
Optimized version with parallel processing
"""
import os
import logging
import uuid
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from threading import Thread
import time

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimExtractor
from services.factcheck import FactChecker
from config import Config

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
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

# Initialize services
transcript_processor = TranscriptProcessor()
claim_extractor = ClaimExtractor(openai_api_key=Config.OPENAI_API_KEY)
fact_checker = FactChecker(Config)

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
        'role': '46th President of the United States',
        'party': 'Democrat',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Occasional misstatements and gaffes',
        'credibility_notes': 'Generally factual with some exaggerations'
    },
    'kamala harris': {
        'full_name': 'Kamala D. Harris',
        'role': 'Former Vice President of the United States',
        'party': 'Democrat',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Generally accurate with some misleading claims',
        'credibility_notes': 'Former VP (2021-2025)'
    }
}

# Storage helper functions
def store_job(job_id: str, job_data: dict):
    """Store job data"""
    try:
        if jobs_collection:
            job_data['_id'] = job_id
            jobs_collection.insert_one(job_data)
        else:
            in_memory_jobs[job_id] = job_data
        
        # Also store in Redis for fast access
        if redis_client:
            redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
    except Exception as e:
        logger.error(f"Error storing job: {e}")
        in_memory_jobs[job_id] = job_data

def get_job(job_id: str) -> dict:
    """Retrieve job data"""
    try:
        # Try Redis first
        if redis_client:
            cached = redis_client.get(f"job:{job_id}")
            if cached:
                return json.loads(cached)
        
        # Try MongoDB
        if jobs_collection:
            job = jobs_collection.find_one({'_id': job_id})
            if job:
                job.pop('_id', None)
                return job
        
        # Fallback to in-memory
        return in_memory_jobs.get(job_id)
    except Exception as e:
        logger.error(f"Error retrieving job: {e}")
        return in_memory_jobs.get(job_id)

def update_job(job_id: str, updates: dict):
    """Update job data"""
    try:
        if jobs_collection:
            jobs_collection.update_one({'_id': job_id}, {'$set': updates})
        else:
            if job_id in in_memory_jobs:
                in_memory_jobs[job_id].update(updates)
        
        # Update Redis cache
        if redis_client:
            job_data = get_job(job_id)
            if job_data:
                job_data.update(updates)
                redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))
    except Exception as e:
        logger.error(f"Error updating job: {e}")
        if job_id in in_memory_jobs:
            in_memory_jobs[job_id].update(updates)

def update_job_progress(job_id: str, progress: int, message: str):
    """Update job progress"""
    update_job(job_id, {
        'progress': progress,
        'message': message,
        'status': 'failed' if progress < 0 else 'processing'
    })

# Routes
@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

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
        }
    })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Analyze transcript endpoint - OPTIMIZED VERSION"""
    try:
        data = request.get_json()
        
        # Validate input
        transcript = data.get('transcript', '').strip()
        source = data.get('source', 'Direct Input')
        
        if not transcript:
            return jsonify({'success': False, 'error': 'No transcript provided'}), 400
        
        if len(transcript) < 50:
            return jsonify({'success': False, 'error': 'Transcript too short'}), 400
        
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({'success': False, 'error': 'Transcript too long'}), 400
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            'status': 'processing',
            'progress': 0,
            'message': 'Initializing...',
            'source': source,
            'created_at': datetime.now().isoformat()
        }
        
        # Store job
        store_job(job_id, job_data)
        
        # Process transcript in background thread to avoid blocking
        thread = Thread(target=process_transcript_async, args=(job_id, transcript, source))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
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
            max_claims=min(Config.MAX_CLAIMS_PER_TRANSCRIPT, 20)  # Limit for speed
        )
        
        # Extract just the claim text for fact checking
        if not claims_data:
            update_job_progress(job_id, 100, 'No verifiable claims found')
            update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'Analysis complete',
                'fact_checks': [],
                'credibility_score': calculate_credibility_score([]),
                'metadata': metadata,
                'source': source,
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
            progress = 30 + int((i / len(claims)) * 60)  # 30% to 90%
            
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
        speakers, topics = claim_extractor.extract_context(transcript)
        speaker_context = analyze_speaker_credibility(speakers, fact_checks)
        
        # Complete (100%)
        update_job_progress(job_id, 100, 'Analysis complete')
        
        # Final results
        results = {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'fact_checks': fact_checks,
            'credibility_score': credibility_score,
            'total_claims': len(claims),
            'processing_time': (datetime.now() - datetime.fromisoformat(
                get_job(job_id)['created_at'])).total_seconds(),
            'speakers': speakers,
            'topics': topics,
            'source': source,
            'metadata': metadata,
            'speaker_context': speaker_context,
            'completed_at': datetime.now().isoformat()
        }
        
        # Store results
        update_job(job_id, results)
        
    except Exception as e:
        logger.error(f"Processing error in job {job_id}: {str(e)}")
        update_job_progress(job_id, -1, f'Error: {str(e)}')
        update_job(job_id, {'status': 'failed', 'error': str(e)})

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        return jsonify({
            'success': True,
            'status': job.get('status'),
            'progress': job.get('progress', 0),
            'message': job.get('message', ''),
            'error': job.get('error')
        })
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    try:
        results = get_job(job_id)
        if not results:
            return jsonify({'success': False, 'error': 'Results not found'}), 404
        
        if results.get('status') != 'completed':
            return jsonify({'success': False, 'error': 'Analysis not completed'}), 400
        
        # Ensure all required fields
        results['success'] = True
        results['job_id'] = job_id
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Results retrieval error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/<job_id>/pdf')
def export_pdf(job_id):
    """Export fact-check results as PDF"""
    try:
        # Get job results
        results = get_job(job_id)
        if not results or results['status'] != 'completed':
            return jsonify({'success': False, 'error': 'Results not available'}), 404
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a202c'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Title
        elements.append(Paragraph("Transcript Fact Check Report", title_style))
        elements.append(Spacer(1, 0.5*inch))
        
        # Summary info
        summary_data = [
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['Source:', results.get('source', 'Unknown')],
            ['Total Claims:', str(results.get('total_claims', 0))],
            ['Processing Time:', f"{results.get('processing_time', 0):.1f} seconds"]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Credibility Score
        score_data = results.get('credibility_score', {})
        score_para = Paragraph(
            f"<b>Overall Credibility Score: {score_data.get('score', 0)}%</b> - {score_data.get('label', 'Unknown')}",
            styles['Heading2']
        )
        elements.append(score_para)
        elements.append(Spacer(1, 0.2*inch))
        
        # Score breakdown
        breakdown_data = [
            ['Metric', 'Count'],
            ['True Claims', str(score_data.get('true_claims', 0))],
            ['False Claims', str(score_data.get('false_claims', 0))],
            ['Unverified Claims', str(score_data.get('unverified_claims', 0))]
        ]
        
        breakdown_table = Table(breakdown_data, colWidths=[2*inch, 1*inch])
        breakdown_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(breakdown_table)
        elements.append(PageBreak())
        
        # Detailed fact checks
        elements.append(Paragraph("Detailed Fact Check Results", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        
        for i, fc in enumerate(results.get('fact_checks', []), 1):
            # Claim
            claim_text = fc.get('claim', 'No claim text')
            elements.append(Paragraph(f"<b>Claim {i}:</b> {claim_text}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            # Verdict
            verdict_color = {
                'true': colors.green,
                'mostly_true': colors.lightgreen,
                'mixed': colors.orange,
                'mostly_false': colors.orangered,
                'false': colors.red,
                'unverified': colors.grey
            }.get(fc.get('verdict', 'unverified'), colors.grey)
            
            verdict_para = Paragraph(
                f"<b>Verdict:</b> <font color='{verdict_color}'>{fc.get('verdict', 'unverified').replace('_', ' ').title()}</font>",
                styles['Normal']
            )
            elements.append(verdict_para)
            
            # Explanation
            if fc.get('explanation'):
                elements.append(Paragraph(f"<b>Explanation:</b> {fc.get('explanation')}", styles['Normal']))
            
            # Sources
            if fc.get('sources'):
                sources_text = ", ".join(fc.get('sources', []))
                elements.append(Paragraph(f"<b>Sources:</b> {sources_text}", styles['Normal']))
            
            elements.append(Spacer(1, 0.3*inch))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'fact-check-report-{job_id}.pdf'
        )
        
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def calculate_credibility_score(fact_checks):
    """Calculate overall credibility score from fact checks"""
    if not fact_checks:
        return {
            'score': 100,
            'label': 'No Claims to Verify',
            'true_claims': 0,
            'false_claims': 0,
            'unverified_claims': 0
        }
    
    true_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['true', 'mostly true', 'mostly_true'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['false', 'mostly false', 'mostly_false', 'misleading', 'deceptive'])
    mixed_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() == 'mixed')
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['unverified', 'unsubstantiated', 'lacks_context'])
    
    total = len(fact_checks)
    
    # Calculate weighted score
    score = ((true_count * 100) + (mixed_count * 50) + (unverified_count * 30)) / total
    
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
        'unverified_claims': unverified_count
    }

def analyze_speaker_credibility(speakers: List[str], fact_checks: List[Dict]) -> Dict:
    """Analyze speaker credibility - OPTIMIZED"""
    speaker_info = {}
    
    # Quick lookup instead of iterating
    speaker_lookup = {}
    for speaker in speakers:
        speaker_lower = speaker.lower()
        for key, info in SPEAKER_DATABASE.items():
            if key in speaker_lower or speaker_lower in key:
                speaker_lookup[speaker] = info
                break
    
    # Process matched speakers
    for speaker, info in speaker_lookup.items():
        speaker_info[speaker] = {
            'full_name': info.get('full_name', speaker),
            'role': info.get('role', 'Unknown'),
            'party': info.get('party', 'Unknown'),
            'credibility_notes': info.get('credibility_notes', ''),
            'historical_accuracy': info.get('fact_check_history', 'No data available')
        }
        
        # Add warnings efficiently
        warnings = []
        if info.get('criminal_record'):
            warnings.append(f"Criminal Record: {info['criminal_record']}")
        if info.get('fraud_history'):
            warnings.append(f"Fraud History: {info['fraud_history']}")
        
        if warnings:
            speaker_info[speaker]['warnings'] = warnings
    
    return speaker_info

if __name__ == '__main__':
    # Validate configuration on startup
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)
