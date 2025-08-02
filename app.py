"""
Transcript Fact Checker - Main Application
A focused tool for fact-checking transcripts from various sources
"""
import os 
import sys
import json
import logging
import uuid
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Debug logging for Render deployment
print(f"Starting app on Render...", file=sys.stderr)
print(f"Python version: {sys.version}", file=sys.stderr)
print(f"Port: {os.environ.get('PORT', 'NOT SET')}", file=sys.stderr)
print(f"Secret Key Set: {'SECRET_KEY' in os.environ}", file=sys.stderr)
print(f"Google API Key Set: {'GOOGLE_FACTCHECK_API_KEY' in os.environ}", file=sys.stderr)

# Import configuration
from config import Config

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimExtractor
from services.factcheck import FactChecker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Validate configuration
Config.validate()

# Initialize services
transcript_processor = TranscriptProcessor()
claim_extractor = ClaimExtractor()
fact_checker = FactChecker()

# In-memory job storage with thread safety
import threading
jobs = {}
jobs_lock = threading.Lock()

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'transcript-factchecker',
        'version': '1.0.0',
        'active_jobs': len(jobs)
    }), 200

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start analysis job"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            input_type = data.get('type', 'text')
        else:
            data = {}
            input_type = request.form.get('type', 'text')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Creating new job: {job_id}")
        
        # Initialize job with thread safety
        with jobs_lock:
            jobs[job_id] = {
                'id': job_id,
                'status': 'processing',
                'progress': 0,
                'created_at': datetime.now().isoformat(),
                'input_type': input_type,
                'results': None,
                'error': None
            }
        
        # Process based on input type
        try:
            if input_type == 'text':
                transcript = data.get('content', '') if request.is_json else request.form.get('content', '')
                if not transcript:
                    raise ValueError("No transcript text provided")
                
                # Process transcript in a separate thread
                thread = threading.Thread(
                    target=process_transcript_async,
                    args=(job_id, transcript, 'Direct Input')
                )
                thread.start()
                
            elif input_type == 'file':
                if 'file' not in request.files:
                    raise ValueError("No file uploaded")
                
                file = request.files['file']
                if file.filename == '':
                    raise ValueError("No file selected")
                
                # Check file extension
                if not allowed_file(file.filename):
                    raise ValueError(f"Invalid file type. Allowed: {', '.join(Config.ALLOWED_EXTENSIONS)}")
                
                # Read file content
                content = file.read().decode('utf-8')
                
                # Process in thread
                thread = threading.Thread(
                    target=process_transcript_async,
                    args=(job_id, content, file.filename)
                )
                thread.start()
                
            elif input_type == 'youtube':
                url = data.get('url', '') if request.is_json else request.form.get('url', '')
                if not url:
                    raise ValueError("No YouTube URL provided")
                
                # Process YouTube URL in thread
                thread = threading.Thread(
                    target=process_youtube_async,
                    args=(job_id, url)
                )
                thread.start()
                
            else:
                raise ValueError(f"Invalid input type: {input_type}")
                
        except Exception as e:
            with jobs_lock:
                jobs[job_id]['status'] = 'error'
                jobs[job_id]['error'] = str(e)
            logger.error(f"Analysis error for job {job_id}: {str(e)}")
        
        logger.info(f"Job {job_id} created successfully")
        
        return jsonify({
            'success': True,
            'job_id': job_id
        })
        
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    logger.debug(f"Status check for job {job_id}")
    
    with jobs_lock:
        if job_id not in jobs:
            logger.error(f"Job {job_id} not found. Available jobs: {list(jobs.keys())}")
            return jsonify({'error': 'Job not found'}), 404
        
        job = jobs[job_id].copy()  # Create a copy to avoid race conditions
    
    logger.debug(f"Job {job_id} status: {job['status']}, progress: {job['progress']}")
    
    return jsonify({
        'id': job['id'],
        'status': job['status'],
        'progress': job['progress'],
        'created_at': job['created_at'],
        'error': job.get('error')
    })

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    logger.debug(f"Getting results for job {job_id}")
    
    with jobs_lock:
        if job_id not in jobs:
            logger.error(f"Job {job_id} not found for results")
            return jsonify({'error': 'Job not found'}), 404
        
        job = jobs[job_id].copy()
    
    if job['status'] != 'complete':
        logger.info(f"Job {job_id} not complete yet. Status: {job['status']}")
        return jsonify({'error': 'Analysis not complete'}), 400
    
    return jsonify({
        'success': True,
        'results': job['results']
    })

@app.route('/api/export/<job_id>', methods=['POST'])
def export_results(job_id):
    """Export results in various formats"""
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        
        job = jobs[job_id].copy()
    
    if job['status'] != 'complete':
        return jsonify({'error': 'Analysis not complete'}), 400
    
    data = request.get_json()
    format_type = data.get('format', 'json')
    
    if format_type not in Config.EXPORT_FORMATS:
        return jsonify({'error': f'Invalid format. Allowed: {", ".join(Config.EXPORT_FORMATS)}'}), 400
    
    try:
        if format_type == 'json':
            # Return JSON file
            filename = f'factcheck_report_{job_id}.json'
            return jsonify({
                'success': True,
                'download_url': f'/api/download/{job_id}/json',
                'filename': filename
            })
        
        elif format_type == 'pdf':
            # Generate PDF (implement in services/export.py)
            filename = f'factcheck_report_{job_id}.pdf'
            return jsonify({
                'success': True,
                'download_url': f'/api/download/{job_id}/pdf',
                'filename': filename
            })
        
        else:
            # Text format
            filename = f'factcheck_report_{job_id}.txt'
            return jsonify({
                'success': True,
                'download_url': f'/api/download/{job_id}/txt',
                'filename': filename
            })
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/download/<job_id>/<format_type>')
def download_file(job_id, format_type):
    """Download exported file"""
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        
        job = jobs[job_id].copy()
    
    if job['status'] != 'complete':
        return jsonify({'error': 'Analysis not complete'}), 400
    
    # Generate file content based on format
    if format_type == 'json':
        content = json.dumps(job['results'], indent=2)
        mimetype = 'application/json'
    elif format_type == 'txt':
        content = generate_text_report(job['results'])
        mimetype = 'text/plain'
    else:
        return jsonify({'error': 'Format not implemented yet'}), 501
    
    # Return file
    return content, 200, {
        'Content-Type': mimetype,
        'Content-Disposition': f'attachment; filename=factcheck_report_{job_id}.{format_type}'
    }

# Helper functions
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def update_job_progress(job_id, progress, status=None):
    """Safely update job progress"""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]['progress'] = progress
            if status:
                jobs[job_id]['status'] = status
            logger.debug(f"Updated job {job_id}: progress={progress}, status={status}")

def process_youtube_async(job_id, url):
    """Process YouTube URL asynchronously"""
    try:
        logger.info(f"Starting YouTube processing for job {job_id}")
        
        # Extract transcript from YouTube
        update_job_progress(job_id, 10)
        transcript_data = transcript_processor.parse_youtube(url)
        
        if not transcript_data['success']:
            raise ValueError(transcript_data.get('error', 'Failed to extract YouTube transcript'))
        
        # Process the transcript
        process_transcript_async(job_id, transcript_data['transcript'], transcript_data['title'])
        
    except Exception as e:
        logger.error(f"YouTube processing error for job {job_id}: {str(e)}")
        with jobs_lock:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = str(e)

def process_transcript_async(job_id, transcript, source):
    """Process transcript asynchronously with proper progress updates"""
    try:
        logger.info(f"Starting transcript processing for job {job_id}")
        
        # Clean transcript
        update_job_progress(job_id, 20)
        cleaned_transcript = transcript_processor.clean_transcript(transcript)
        
        # Extract claims
        update_job_progress(job_id, 40)
        claims = claim_extractor.extract_claims(cleaned_transcript)
        logger.info(f"Job {job_id}: Extracted {len(claims)} claims")
        
        # Prioritize and filter claims
        update_job_progress(job_id, 50)
        verified_claims = claim_extractor.filter_verifiable(claims)
        prioritized_claims = claim_extractor.prioritize_claims(verified_claims)
        
        # Limit claims to process
        claims_to_check = prioritized_claims[:Config.MAX_CLAIMS_PER_TRANSCRIPT]
        logger.info(f"Job {job_id}: Checking {len(claims_to_check)} prioritized claims")
        
        # Fact check claims
        update_job_progress(job_id, 70)
        fact_check_results = []
        
        for idx, claim in enumerate(claims_to_check):
            # Update progress
            progress = 70 + (20 * idx / len(claims_to_check))
            update_job_progress(job_id, progress)
            
            # Check claim
            try:
                result = fact_checker.check_claim(claim)
                fact_check_results.append(result)
                logger.debug(f"Job {job_id}: Checked claim {idx+1}/{len(claims_to_check)}")
            except Exception as e:
                logger.error(f"Error checking claim '{claim}': {str(e)}")
                fact_check_results.append({
                    'claim': claim,
                    'verdict': 'unverified',
                    'confidence': 0,
                    'explanation': f'Error during fact-checking: {str(e)}',
                    'sources': []
                })
            
            # Rate limiting
            if idx < len(claims_to_check) - 1:
                time.sleep(Config.FACT_CHECK_RATE_LIMIT_DELAY)
        
        # Calculate overall credibility
        update_job_progress(job_id, 90)
        credibility_score = fact_checker.calculate_credibility(fact_check_results)
        
        # Generate summary
        summary = generate_enhanced_summary(fact_check_results, credibility_score, claims)
        
        # Compile results
        results = {
            'source': source,
            'transcript_length': len(transcript),
            'word_count': len(transcript.split()),
            'total_claims': len(claims),
            'verified_claims': len(verified_claims),
            'checked_claims': len(fact_check_results),
            'credibility_score': credibility_score,
            'credibility_label': get_credibility_label(credibility_score),
            'fact_checks': fact_check_results,
            'summary': summary,
            'analysis_notes': generate_analysis_notes(fact_check_results),
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Complete job
        with jobs_lock:
            jobs[job_id]['progress'] = 100
            jobs[job_id]['status'] = 'complete'
            jobs[job_id]['results'] = results
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}", exc_info=True)
        with jobs_lock:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = str(e)

def process_transcript(job_id, transcript, source):
    """Legacy synchronous processing function - redirects to async version"""
    process_transcript_async(job_id, transcript, source)

def get_credibility_label(score):
    """Convert credibility score to label"""
    if score >= 80:
        return "High Credibility"
    elif score >= 60:
        return "Moderate Credibility"
    elif score >= 40:
        return "Low Credibility"
    else:
        return "Very Low Credibility"

def generate_enhanced_summary(fact_checks, credibility_score, all_claims):
    """Generate an enhanced analysis summary"""
    verified_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['true', 'mostly_true'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['false', 'mostly_false'])
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict') == 'unverified')
    
    summary = f"Analysis complete. Out of {len(fact_checks)} claims checked: "
    summary += f"{verified_count} verified as true, {false_count} found to be false, "
    summary += f"and {unverified_count} could not be verified. "
    summary += f"Overall credibility score: {credibility_score}%."
    
    # Add specific warnings for low credibility
    if credibility_score < 40:
        summary += "\n\n⚠️ Warning: This transcript contains multiple false or misleading claims. "
        summary += "Readers should verify information from authoritative sources."
    elif credibility_score < 60:
        summary += "\n\n⚠️ Caution: This transcript contains a mix of accurate and inaccurate information. "
        summary += "Critical evaluation of specific claims is recommended."
    
    return summary

def generate_analysis_notes(fact_checks):
    """Generate important notes about the analysis"""
    notes = []
    
    # Check for patterns
    false_claims = [fc for fc in fact_checks if fc.get('verdict') in ['false', 'mostly_false']]
    if len(false_claims) > 3:
        notes.append("Multiple false claims detected. This may indicate systematic misinformation.")
    
    # Check source diversity
    all_sources = []
    for fc in fact_checks:
        if fc.get('sources'):
            all_sources.extend(fc['sources'])
    
    unique_sources = set(all_sources)
    if len(unique_sources) < 3:
        notes.append("Limited verification sources available. Results may benefit from additional fact-checking.")
    
    return notes

def generate_text_report(results):
    """Generate plain text report"""
    report = f"""TRANSCRIPT FACT-CHECK REPORT
Generated: {results['analyzed_at']}
Source: {results['source']}

OVERVIEW
--------
Total Claims Identified: {results['total_claims']}
Claims Checked: {results['checked_claims']}
Credibility Score: {results['credibility_score']}% ({results['credibility_label']})

SUMMARY
-------
{results['summary']}

"""
    
    # Add analysis notes if present
    if results.get('analysis_notes'):
        report += "ANALYSIS NOTES\n--------------\n"
        for note in results['analysis_notes']:
            report += f"• {note}\n"
        report += "\n"
    
    report += "DETAILED FACT CHECKS\n-------------------\n"
    
    for i, fc in enumerate(results['fact_checks'], 1):
        report += f"\n{i}. CLAIM: {fc['claim']}\n"
        report += f"   VERDICT: {fc['verdict'].upper()}\n"
        report += f"   CONFIDENCE: {fc.get('confidence', 'N/A')}%\n"
        if fc.get('explanation'):
            report += f"   EXPLANATION: {fc['explanation']}\n"
        if fc.get('sources'):
            report += f"   SOURCES: {', '.join(fc['sources'])}\n"
    
    return report

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# Add a catch-all error handler for debugging
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Log startup information
    logger.info(f"Starting Flask app on port {port}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Active APIs: {Config.get_active_apis()}")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
