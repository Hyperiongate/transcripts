"""
Transcript Fact Checker - Main Flask Application
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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from functools import partial

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

# Create a thread pool for background processing
executor = ThreadPoolExecutor(max_workers=4)

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
        'fact_check_history': 'Mix of accurate and inaccurate statements; known for verbal gaffes',
        'credibility_notes': 'Generally factual but prone to exaggeration and misremembering details'
    },
    'kamala harris': {
        'full_name': 'Kamala D. Harris',
        'role': 'Vice President of the United States',
        'party': 'Democrat',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Generally accurate with occasional misstatements',
        'credibility_notes': 'Professional prosecutor background; generally careful with facts'
    }
}

# Storage helper functions
def store_job(job_id, data):
    """Store job data in available storage"""
    if jobs_collection is not None:
        try:
            jobs_collection.insert_one({**data, 'job_id': job_id})
            return True
        except Exception as e:
            logger.error(f"MongoDB insert error: {str(e)}")
    
    # Fallback to in-memory
    in_memory_jobs[job_id] = data
    return True

def get_job(job_id):
    """Retrieve job data from available storage"""
    if jobs_collection is not None:
        try:
            job = jobs_collection.find_one({'job_id': job_id})
            if job:
                job.pop('_id', None)
                return job
        except Exception as e:
            logger.error(f"MongoDB query error: {str(e)}")
    
    # Fallback to in-memory
    return in_memory_jobs.get(job_id)

def update_job(job_id, updates):
    """Update job data in available storage"""
    if jobs_collection is not None:
        try:
            jobs_collection.update_one(
                {'job_id': job_id},
                {'$set': updates}
            )
            return True
        except Exception as e:
            logger.error(f"MongoDB update error: {str(e)}")
    
    # Fallback to in-memory
    if job_id in in_memory_jobs:
        in_memory_jobs[job_id].update(updates)
    return True

def update_job_progress(job_id, progress, message):
    """Update job progress in storage"""
    logger.info(f"Job {job_id}: {progress}% - {message}")
    update_job(job_id, {
        'progress': progress,
        'message': message,
        'updated_at': datetime.now().isoformat()
    })

def check_single_claim(claim, index, total, job_id, metadata):
    """Check a single claim and update progress"""
    try:
        # Update progress
        progress = 45 + int((index / total) * 45)  # 45% to 90%
        update_job_progress(job_id, progress, f'Checking claim {index+1} of {total}')
        
        # Create context for this claim
        claim_context = {
            'metadata': metadata,
            'claim_index': index,
            'total_claims': total
        }
        
        # Check the claim with a shorter timeout
        fact_check_results = fact_checker.check_claims([claim], context=claim_context)
        
        if fact_check_results:
            return fact_check_results[0]
        else:
            return {
                'claim': claim,
                'verdict': 'unverified',
                'confidence': 0,
                'explanation': 'Unable to verify this claim',
                'sources': []
            }
    except Exception as e:
        logger.error(f"Error checking claim {index+1}: {str(e)}")
        return {
            'claim': claim,
            'verdict': 'error',
            'confidence': 0,
            'explanation': f'Error during fact-check: {str(e)}',
            'sources': []
        }

def process_transcript_robust(job_id, transcript, source, metadata):
    """Process transcript with robust error handling and progress updates"""
    try:
        # Step 3: Extract claims (30-40%)
        update_job_progress(job_id, 30, 'Extracting factual claims...')
        
        # Use a timeout for claim extraction
        try:
            claims_data = claim_extractor.extract_claims(transcript, max_claims=Config.MAX_CLAIMS_PER_TRANSCRIPT)
        except Exception as e:
            logger.error(f"Claim extraction error: {str(e)}")
            # Fallback to basic extraction
            sentences = transcript.split('.')
            claims_data = [{'text': s.strip()} for s in sentences if len(s.strip()) > 50][:20]
        
        # Extract just the claim text for fact checking
        if not claims_data:
            claims = []
        elif isinstance(claims_data[0], str):
            claims = claims_data
        else:
            claims = [c.get('text', c) if isinstance(c, dict) else str(c) for c in claims_data]
        
        update_job_progress(job_id, 40, f'Found {len(claims)} claims to verify')
        
        if not claims:
            update_job_progress(job_id, 100, 'No verifiable claims found')
            results = {
                'status': 'completed',
                'claims': [],
                'fact_checks': [],
                'credibility_score': 100,
                'credibility_label': 'No Claims to Verify',
                'total_claims': 0,
                'true_claims': 0,
                'false_claims': 0,
                'unverified_claims': 0,
                'source': source,
                'metadata': metadata
            }
            update_job(job_id, results)
            return
        
        # Step 4: Fact check claims in smaller batches
        update_job_progress(job_id, 45, f'Starting fact-check of {len(claims)} claims...')
        fact_checks = []
        
        # Process claims in batches of 5
        batch_size = 5
        for i in range(0, len(claims), batch_size):
            batch = claims[i:i+batch_size]
            batch_start = i
            
            # Update progress for this batch
            batch_progress = 45 + int((i / len(claims)) * 45)
            update_job_progress(job_id, batch_progress, f'Checking claims {i+1} to {min(i+batch_size, len(claims))}')
            
            # Check each claim in the batch
            for j, claim in enumerate(batch):
                try:
                    result = check_single_claim(claim, batch_start + j, len(claims), job_id, metadata)
                    fact_checks.append(result)
                    
                    # Small delay to prevent API rate limiting
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error in batch processing: {str(e)}")
                    fact_checks.append({
                        'claim': claim,
                        'verdict': 'error',
                        'confidence': 0,
                        'explanation': 'Processing error',
                        'sources': []
                    })
        
        # Step 5: Calculate credibility score (90-95%)
        update_job_progress(job_id, 90, 'Calculating credibility score...')
        credibility_data = calculate_credibility_score(fact_checks)
        
        # Step 6: Complete (95-100%)
        update_job_progress(job_id, 95, 'Finalizing results...')
        
        # Get speaker context
        speaker = None
        if metadata.get('speakers'):
            speaker = metadata['speakers'][0] if metadata['speakers'] else None
        
        speaker_context = {}
        if speaker:
            speaker_lower = speaker.lower()
            for key, value in SPEAKER_DATABASE.items():
                if key in speaker_lower or speaker_lower in key:
                    speaker_context = value.copy()
                    speaker_context['speaker'] = speaker
                    break
        
        # Prepare results
        results = {
            'status': 'completed',
            'claims': claims,
            'fact_checks': fact_checks,
            'credibility_score': credibility_data['score'],
            'credibility_label': credibility_data['label'],
            'true_claims': credibility_data['true_claims'],
            'false_claims': credibility_data['false_claims'],
            'unverified_claims': credibility_data['unverified_claims'],
            'total_claims': len(claims),
            'source': source,
            'metadata': metadata,
            'speaker_context': speaker_context,
            'completed_at': datetime.now().isoformat()
        }
        
        # Store results
        update_job(job_id, results)
        update_job_progress(job_id, 100, 'Analysis complete!')
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        update_job_progress(job_id, -1, f'Error: {str(e)}')
        update_job(job_id, {'status': 'failed', 'error': str(e)})

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
    """Analyze transcript endpoint"""
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
            'message': 'Starting analysis...',
            'source': source,
            'created_at': datetime.now().isoformat()
        }
        
        # Store job
        store_job(job_id, job_data)
        
        # Process initial steps
        try:
            # Step 1: Process transcript (10%)
            update_job_progress(job_id, 10, 'Processing transcript...')
            processed_transcript = transcript_processor.process(transcript)
            
            # Step 2: Extract metadata (20%)
            update_job_progress(job_id, 20, 'Extracting metadata...')
            metadata = transcript_processor.extract_metadata(processed_transcript)
            
            # Submit to thread pool for processing
            future = executor.submit(
                process_transcript_robust,
                job_id,
                processed_transcript,
                source,
                metadata
            )
            
            # Store the future reference (optional, for tracking)
            if hasattr(app, 'active_jobs'):
                app.active_jobs[job_id] = future
            else:
                app.active_jobs = {job_id: future}
            
            # Return immediately with job ID
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': 'Analysis started successfully'
            })
            
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            update_job_progress(job_id, -1, f'Error: {str(e)}')
            update_job(job_id, {'status': 'failed', 'error': str(e)})
            return jsonify({'success': False, 'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status with detailed progress"""
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Check if job is still active
        if hasattr(app, 'active_jobs') and job_id in app.active_jobs:
            future = app.active_jobs[job_id]
            if future.done():
                # Clean up completed job
                del app.active_jobs[job_id]
        
        # Always return current progress
        return jsonify({
            'success': True,
            'status': job.get('status', 'unknown'),
            'progress': job.get('progress', 0),
            'message': job.get('message', ''),
            'error': job.get('error'),
            'updated_at': job.get('updated_at')
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
            return jsonify({'success': False, 'error': 'Results not found or not ready'}), 404
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12
        )
        
        # Title
        elements.append(Paragraph("Transcript Fact Check Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Date
        date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        elements.append(Paragraph(f"Generated on {date_str}", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Summary Section
        elements.append(Paragraph("Executive Summary", heading_style))
        
        # Credibility Score
        credibility = results.get('credibility_score', 0)
        credibility_label = results.get('credibility_label', 'Unknown')
        elements.append(Paragraph(f"<b>Overall Credibility Score:</b> {credibility}% ({credibility_label})", styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Stats table
        stats_data = [
            ['Metric', 'Count'],
            ['Total Claims', str(results.get('total_claims', 0))],
            ['Verified True', str(results.get('true_claims', 0))],
            ['Verified False', str(results.get('false_claims', 0))],
            ['Unverified', str(results.get('unverified_claims', 0))]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb'))
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Return PDF
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

# Cleanup function
def cleanup_old_jobs():
    """Clean up old jobs from memory"""
    if hasattr(app, 'active_jobs'):
        completed = []
        for job_id, future in app.active_jobs.items():
            if future.done():
                completed.append(job_id)
        for job_id in completed:
            del app.active_jobs[job_id]

if __name__ == '__main__':
    # Validate configuration on startup
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=lambda: cleanup_old_jobs(), daemon=True)
    cleanup_thread.start()
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)
