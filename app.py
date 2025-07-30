"""
Transcript Fact Checker - Main Application
A focused tool for fact-checking transcripts from various sources
"""
import os 
import json
import logging
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import configuration
from config import Config

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimExtractor
from services.factcheck import FactChecker

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# In-memory job storage (replace with Redis in production)
jobs = {}

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start analysis job"""
    try:
        data = request.get_json() if request.is_json else {}
        input_type = data.get('type', 'text')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job
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
                transcript = data.get('content', '')
                if not transcript:
                    raise ValueError("No transcript text provided")
                
                # Process transcript
                process_transcript(job_id, transcript, 'Direct Input')
                
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
                process_transcript(job_id, content, file.filename)
                
            elif input_type == 'youtube':
                url = data.get('url', '')
                if not url:
                    raise ValueError("No YouTube URL provided")
                
                # Extract transcript from YouTube
                jobs[job_id]['progress'] = 10
                transcript_data = transcript_processor.parse_youtube(url)
                
                if not transcript_data['success']:
                    raise ValueError(transcript_data.get('error', 'Failed to extract YouTube transcript'))
                
                process_transcript(job_id, transcript_data['transcript'], transcript_data['title'])
                
            else:
                raise ValueError(f"Invalid input type: {input_type}")
                
        except Exception as e:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = str(e)
            logger.error(f"Analysis error for job {job_id}: {str(e)}")
        
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
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
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
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    if job['status'] != 'complete':
        return jsonify({'error': 'Analysis not complete'}), 400
    
    return jsonify({
        'success': True,
        'results': job['results']
    })

@app.route('/api/export/<job_id>', methods=['POST'])
def export_results(job_id):
    """Export results in various formats"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
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
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
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

def process_transcript(job_id, transcript, source):
    """Process transcript through the fact-checking pipeline"""
    try:
        job = jobs[job_id]
        
        # Clean transcript
        job['progress'] = 20
        cleaned_transcript = transcript_processor.clean_transcript(transcript)
        
        # Extract claims
        job['progress'] = 40
        claims = claim_extractor.extract_claims(cleaned_transcript)
        logger.info(f"Extracted {len(claims)} claims from transcript")
        
        # Prioritize and filter claims
        job['progress'] = 50
        verified_claims = claim_extractor.filter_verifiable(claims)
        prioritized_claims = claim_extractor.prioritize_claims(verified_claims)
        
        # Fact check claims
        job['progress'] = 70
        fact_check_results = fact_checker.batch_check(prioritized_claims[:Config.MAX_CLAIMS_PER_TRANSCRIPT])
        
        # Calculate overall credibility
        job['progress'] = 90
        credibility_score = fact_checker.calculate_credibility(fact_check_results)
        
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
            'summary': generate_summary(fact_check_results, credibility_score),
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Complete job
        job['progress'] = 100
        job['status'] = 'complete'
        job['results'] = results
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        job['status'] = 'error'
        job['error'] = str(e)

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

def generate_summary(fact_checks, credibility_score):
    """Generate analysis summary"""
    verified_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['true', 'mostly_true'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['false', 'mostly_false'])
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict') == 'unverified')
    
    summary = f"Analysis complete. Out of {len(fact_checks)} claims checked: "
    summary += f"{verified_count} verified as true, {false_count} found to be false, "
    summary += f"and {unverified_count} could not be verified. "
    summary += f"Overall credibility score: {credibility_score}%."
    
    return summary

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

DETAILED FACT CHECKS
-------------------
"""
    
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
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
