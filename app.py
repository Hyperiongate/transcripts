"""
AI-Powered Transcript Fact Checker
Main Flask application
"""
import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Dict, List, Optional, Any, Tuple

# Import all services
from services.audio_processor import AudioProcessor
from services.transcript_analyzer import TranscriptAnalyzer
from services.comprehensive_factcheck import ComprehensiveFactChecker
from services.export import PDFExporter
from services.job_manager import JobManager
from services.context_aware_summarizer import ContextAwareSummarizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXPORT_FOLDER'] = 'exports'

# Ensure required directories exist
for folder in ['uploads', 'exports', 'temp']:
    os.makedirs(folder, exist_ok=True)

# Initialize services
audio_processor = AudioProcessor()
transcript_analyzer = TranscriptAnalyzer()
fact_checker = ComprehensiveFactChecker()
pdf_exporter = PDFExporter()
job_manager = JobManager()
summarizer = ContextAwareSummarizer()

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=4)

# Helper functions
def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'flac', 'm4a', 'webm'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_job_progress(job_id: str, progress: int, status_message: str):
    """Update job progress"""
    job_manager.update_job(job_id, {
        'progress': progress,
        'status_message': status_message,
        'last_updated': datetime.now().isoformat()
    })

def run_async(coro):
    """Run async coroutine in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start processing"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload an audio or video file.'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            'id': job_id,
            'status': 'processing',
            'progress': 0,
            'filename': filename,
            'filepath': filepath,
            'created': datetime.now().isoformat(),
            'status_message': 'Starting processing...'
        }
        job_manager.create_job(job_id, job_data)
        
        # Start processing in background
        executor.submit(process_transcript, job_id, filepath)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'File uploaded successfully. Processing started.'
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_text', methods=['POST'])
def analyze_text():
    """Analyze pasted text transcript"""
    try:
        data = request.get_json()
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        if len(transcript) < 50:
            return jsonify({'error': 'Transcript too short. Please provide more content.'}), 400
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            'id': job_id,
            'status': 'processing',
            'progress': 0,
            'source_type': 'text',
            'created': datetime.now().isoformat(),
            'status_message': 'Starting analysis...'
        }
        job_manager.create_job(job_id, job_data)
        
        # Start processing in background
        executor.submit(process_text_transcript, job_id, transcript)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Analysis started.'
        })
        
    except Exception as e:
        logger.error(f"Text analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/job/<job_id>')
def get_job_status(job_id):
    """Get job status and results"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job)
        
    except Exception as e:
        logger.error(f"Job status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/results/<job_id>')
def view_results(job_id):
    """View results page"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            return render_template('error.html', error="Results not found"), 404
        
        if job['status'] != 'completed':
            return redirect(url_for('processing', job_id=job_id))
        
        return render_template('results.html', results=job, job_id=job_id)
        
    except Exception as e:
        logger.error(f"Results view error: {e}")
        return render_template('error.html', error=str(e)), 500

@app.route('/processing/<job_id>')
def processing(job_id):
    """Processing status page"""
    return render_template('processing.html', job_id=job_id)

@app.route('/export/<job_id>')
def export_results(job_id):
    """Export results as PDF"""
    try:
        job = job_manager.get_job(job_id)
        if not job or job['status'] != 'completed':
            return jsonify({'error': 'Results not ready for export'}), 400
        
        # Generate PDF
        pdf_path = pdf_exporter.export_to_pdf(job)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'fact_check_report_{job_id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/demo')
def demo():
    """Demo page with example transcripts"""
    return render_template('demo.html')

@app.route('/api/check_claim', methods=['POST'])
def api_check_claim():
    """API endpoint for single claim checking"""
    try:
        data = request.get_json()
        claim = data.get('claim', '').strip()
        
        if not claim:
            return jsonify({'error': 'No claim provided'}), 400
        
        # Check single claim
        result = run_async(fact_checker.check_claim_comprehensive(claim, {}))
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"API check error: {e}")
        return jsonify({'error': str(e)}), 500

# Processing functions
def process_transcript(job_id: str, filepath: str):
    """Process uploaded audio/video file"""
    try:
        # Update progress
        update_job_progress(job_id, 10, "Extracting audio from file...")
        
        # Extract transcript
        transcript_data = audio_processor.extract_transcript(filepath)
        
        if not transcript_data or not transcript_data.get('transcript'):
            raise Exception("Failed to extract transcript from audio")
        
        transcript = transcript_data['transcript']
        
        # Continue with text processing
        process_text_transcript(job_id, transcript, source_type='audio')
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {e}")
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': str(e),
            'completed': datetime.now().isoformat()
        })
    finally:
        # Cleanup uploaded file
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass

def process_text_transcript(job_id: str, transcript: str, source_type: str = 'text'):
    """Process text transcript"""
    try:
        # Update progress
        update_job_progress(job_id, 20, "Analyzing transcript structure...")
        
        # Analyze transcript
        claims_data = transcript_analyzer.extract_claims_enhanced(transcript)
        
        if not claims_data.get('claims'):
            raise Exception("No verifiable claims found in transcript")
        
        # Extract data
        claims = claims_data.get('claims', [])
        speakers = claims_data.get('speakers', {})
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
                result = run_async(fact_checker.check_claim_comprehensive(
                    claim['text'],
                    {
                        'speaker': claim.get('speaker', 'Unknown'),
                        'context': claim.get('context', '')
                    }
                ))
                
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
        
        # Generate enhanced summary
        summary_results = {
            'credibility_score': credibility_score,
            'fact_checks': fact_checks,
            'total_claims': len(claims),
            'speakers': speakers,
            'topics': topics
        }
        enhanced_summary = summarizer.generate_summary(summary_results)
        
        # Prepare final results
        results = {
            'job_id': job_id,
            'status': 'completed',
            'created': datetime.now().isoformat(),
            'source_type': source_type,
            'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
            'total_claims': len(claims),
            'checked_claims': len(fact_checks),
            'speakers': speakers,
            'topics': topics,
            'fact_checks': fact_checks,
            'credibility_score': credibility_score,
            'enhanced_summary': enhanced_summary,
            'completed': datetime.now().isoformat()
        }
        
        # Save results
        job_manager.update_job(job_id, results)
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {e}")
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': str(e),
            'completed': datetime.now().isoformat()
        })

def calculate_credibility_score_enhanced(fact_checks: List[Dict]) -> Dict:
    """Calculate enhanced credibility score based on verdicts"""
    if not fact_checks:
        return {
            'score': 0,
            'label': 'No claims to evaluate',
            'verdict_counts': {},
            'total_claims': 0
        }
    
    # Count verdicts
    verdict_counts = {}
    total_score = 0
    scorable_claims = 0
    
    # Verdict scoring weights
    verdict_scores = {
        'verified_true': 100,
        'verified_false': 0,
        'partially_accurate': 50,
        'misleading': 20,
        'opinion': None,  # Don't score opinions
        'unverifiable': None,  # Don't score unverifiable
        'needs_context': None
    }
    
    for fc in fact_checks:
        verdict = fc.get('verdict', 'unverifiable')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        # Calculate score
        if verdict in verdict_scores and verdict_scores[verdict] is not None:
            total_score += verdict_scores[verdict]
            scorable_claims += 1
    
    # Calculate weighted score
    if scorable_claims > 0:
        score = total_score / scorable_claims
    else:
        score = 50  # Default to middle if no scorable claims
    
    # Determine overall label
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
            'opinion': verdict_counts.get('opinion', 0),
            'misleading': verdict_counts.get('misleading', 0),
            'needs_context': verdict_counts.get('needs_context', 0)
        }
    }

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', error="Internal server error"), 500

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 100MB.'}), 413

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Main entry point
if __name__ == '__main__':
    # Check for required environment variables
    required_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set these in your .env file or environment")
        exit(1)
    
    # Get port from environment or default
    port = int(os.getenv('PORT', 5000))
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False  # Never use debug=True in production
    )
