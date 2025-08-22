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
    partially_accurate = verdict_counts.get('partially_accurate', 0)
    unverifiable = verdict_counts.get('unverifiable', 0)
    
    if verified_true > 0 and verified_false == 0 and score >= 85:
        label = 'Highly Credible - Claims Verified'
    elif verified_true > verified_false and score >= 70:
        label = 'Generally Credible - Mostly Verified'
    elif verified_false > verified_true:
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
            'verified_false': verified_false,
            'partially_accurate': partially_accurate,
            'unverifiable': unverifiable,
            'opinion': verdict_counts.get('opinion', 0)
        }
    }

def generate_enhanced_conversational_summary(results: Dict) -> str:
    """Generate a clear summary with verification focus"""
    
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
    
    # Verification breakdown
    summary_parts.append(f"\n🔍 Verification Results:")
    
    verified_true = verdict_counts.get('verified_true', 0)
    verified_false = verdict_counts.get('verified_false', 0)
    partially_accurate = verdict_counts.get('partially_accurate', 0)
    unverifiable = verdict_counts.get('unverifiable', 0)
    opinion = verdict_counts.get('opinion', 0)
    
    if verified_true > 0:
        summary_parts.append(f"• ✅ Verified True: {verified_true} claims")
    if verified_false > 0:
        summary_parts.append(f"• ❌ Verified False: {verified_false} claims")
    if partially_accurate > 0:
        summary_parts.append(f"• ⚠️ Partially Accurate: {partially_accurate} claims")
    if unverifiable > 0:
        summary_parts.append(f"• ❓ Could Not Verify: {unverifiable} claims")
    if opinion > 0:
        summary_parts.append(f"• 💭 Opinions (not fact-checked): {opinion} statements")
    
    # Key findings
    if verified_false >= 3:
        summary_parts.append(f"\n⚠️ WARNING: Multiple false claims detected ({verified_false} total)")
    elif verified_false > 0:
        summary_parts.append(f"\n⚠️ Note: {verified_false} false claim(s) were identified")
    
    if verified_true >= 5:
        summary_parts.append(f"\n✅ Positive: Many claims were verified as accurate ({verified_true} total)")
    
    if unverifiable >= 5:
        summary_parts.append(f"\n❓ Note: Many claims could not be verified with available sources ({unverifiable} total)")
    
    # Most significant false claims
    false_claims = [fc for fc in results.get('fact_checks', []) if fc.get('verdict') == 'verified_false']
    if false_claims:
        summary_parts.append("\n🚨 Key False Claims:")
        for i, fc in enumerate(false_claims[:3], 1):
            claim_preview = fc.get('claim', '')[:100] + '...' if len(fc.get('claim', '')) > 100 else fc.get('claim', '')
            summary_parts.append(f"{i}. \"{claim_preview}\"")
    
    # Conclusion
    if score >= 85 and verified_false == 0:
        summary_parts.append("\n✅ Conclusion: This transcript contains highly accurate information.")
    elif score >= 70:
        summary_parts.append("\n✓ Conclusion: This transcript is generally accurate with some issues.")
    elif score >= 50:
        summary_parts.append("\n⚠️ Conclusion: This transcript contains a mix of true and false information.")
    else:
        summary_parts.append("\n❌ Conclusion: This transcript contains significant inaccuracies.")
    
    return '\n'.join(summary_parts)

def analyze_speaker_credibility(speakers: List[str], fact_checks: List[Dict]) -> Dict:
    """Analyze credibility by speaker"""
    speaker_stats = {}
    
    for fc in fact_checks:
        speaker = fc.get('speaker', 'Unknown')
        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                'total_claims': 0,
                'verified_true': 0,
                'verified_false': 0,
                'partially_accurate': 0,
                'unverifiable': 0,
                'opinion': 0
            }
        
        speaker_stats[speaker]['total_claims'] += 1
        verdict = fc.get('verdict', 'unverifiable')
        
        if verdict == 'verified_true':
            speaker_stats[speaker]['verified_true'] += 1
        elif verdict == 'verified_false':
            speaker_stats[speaker]['verified_false'] += 1
        elif verdict == 'partially_accurate':
            speaker_stats[speaker]['partially_accurate'] += 1
        elif verdict == 'unverifiable':
            speaker_stats[speaker]['unverifiable'] += 1
        elif verdict == 'opinion':
            speaker_stats[speaker]['opinion'] += 1
    
    # Calculate accuracy for each speaker
    for speaker, stats in speaker_stats.items():
        verifiable = stats['verified_true'] + stats['verified_false'] + stats['partially_accurate']
        if verifiable > 0:
            accuracy = (stats['verified_true'] + 0.5 * stats['partially_accurate']) / verifiable * 100
            stats['accuracy_rate'] = round(accuracy)
        else:
            stats['accuracy_rate'] = None
        
        # Add speaker info from database
        speaker_key = speaker.lower()
        if speaker_key in SPEAKER_DATABASE:
            stats.update(SPEAKER_DATABASE[speaker_key])
    
    return speaker_stats

# Background fact checking
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
        update_job_progress(job_id, 30, f"Verifying {len(claims)} claims...")
        
        # Fact check each claim
        fact_checks = []
        for i, claim in enumerate(claims):
            try:
                # Update progress
                progress = 30 + int((i / len(claims)) * 60)
                update_job_progress(job_id, progress, f"Verifying claim {i+1} of {len(claims)}...")
                
                # Fact check with enhanced verification
                result = fact_checker.check_claim_with_verdict(claim['text'])
                result['speaker'] = claim.get('speaker', 'Unknown')
                result['claim'] = claim['text']
                result['context'] = claim.get('context', '')
                fact_checks.append(result)
                
            except Exception as e:
                logger.error(f"Error checking claim {i}: {e}")
                fact_checks.append({
                    'claim': claim['text'],
                    'verdict': 'unverifiable',
                    'explanation': f"Error during verification: {str(e)}",
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
            'status': 'completed',
            'created': datetime.now().isoformat(),
            'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
            'total_claims': len(claims),
            'speakers': speakers,
            'topics': topics,
            'fact_checks': fact_checks,
            'credibility_score': credibility_score,
            'speaker_analysis': speaker_context,
            'conversational_summary': generate_enhanced_conversational_summary({
                'credibility_score': credibility_score,
                'fact_checks': fact_checks,
                'total_claims': len(claims)
            })
        }
        
        # Update job with results
        update_job(job_id, {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'results': results
        })
        
        logger.info(f"Fact check completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error in fact check process: {str(e)}")
        logger.error(traceback.format_exc())
        update_job(job_id, {
            'status': 'failed',
            'progress': -1,
            'message': f'Analysis failed: {str(e)}',
            'error': str(e)
        })

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start analysis"""
    try:
        data = request.json
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        if len(transcript) > 50000:
            return jsonify({'error': 'Transcript too long (max 50,000 characters)'}), 400
        
        # Create job
        job_id = create_job(transcript)
        
        # Start background processing
        thread = threading.Thread(
            target=process_fact_check,
            args=(job_id, transcript)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'processing'
        })
        
    except Exception as e:
        logger.error(f"Error in analyze endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job_id,
            'status': job.get('status', 'unknown'),
            'progress': job.get('progress', 0),
            'message': job.get('message', ''),
            'error': job.get('error')
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get job results"""
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job.get('status') != 'completed':
            return jsonify({'error': 'Job not completed'}), 400
        
        results = job.get('results', {})
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<job_id>/<format>')
def export_results(job_id, format):
    """Export results in various formats"""
    try:
        job = get_job(job_id)
        if not job or job.get('status') != 'completed':
            return jsonify({'error': 'Results not available'}), 404
        
        results = job.get('results', {})
        
        if format == 'json':
            filepath = os.path.join(Config.EXPORT_FOLDER, f'{job_id}.json')
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            return send_file(filepath, as_attachment=True, download_name=f'factcheck_{job_id}.json')
        
        elif format == 'csv':
            import csv
            filepath = os.path.join(Config.EXPORT_FOLDER, f'{job_id}.csv')
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Claim', 'Speaker', 'Verdict', 'Explanation', 'Confidence', 'Sources'])
                
                for fc in results.get('fact_checks', []):
                    writer.writerow([
                        fc.get('claim', ''),
                        fc.get('speaker', 'Unknown'),
                        fc.get('verdict', 'Unknown'),
                        fc.get('explanation', ''),
                        fc.get('confidence', ''),
                        ', '.join(fc.get('sources', []))
                    ])
            
            return send_file(filepath, as_attachment=True, download_name=f'factcheck_{job_id}.csv')
        
        elif format == 'pdf':
            # Import PDF libraries
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            filepath = os.path.join(Config.EXPORT_FOLDER, f'{job_id}.pdf')
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1e40af'),
                spaceAfter=30
            )
            story.append(Paragraph("Political Fact Check Report", title_style))
            story.append(Spacer(1, 0.3*inch))
            
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
            story.append(Paragraph(f"<b>Overall Accuracy Score: {cred_score.get('score', 0)}%</b>", styles['Heading2']))
            story.append(Paragraph(f"Assessment: {cred_score.get('label', 'Unknown')}", styles['Normal']))
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
            table = Table(table_data, colWidths=[3*inch, 1.5*inch, 2.5*inch])
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
            
            return send_file(filepath, as_attachment=True, download_name=f'factcheck_{job_id}.pdf')
        
        else:
            return jsonify({'error': 'Invalid format'}), 400
            
    except Exception as e:
        logger.error(f"Error exporting results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'transcript_processor': 'ready',
            'claim_extractor': 'ready' if claim_extractor else 'not initialized',
            'fact_checker': 'ready' if fact_checker else 'not initialized',
            'mongodb': 'connected' if mongo_client else 'not connected',
            'redis': 'connected' if redis_client else 'not connected'
        }
    })

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# Run app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
