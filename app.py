"""
Transcript Fact Checker - Main Flask Application
"""
import os
import json
import uuid
import time
import logging
import traceback
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import configuration
from config import Config

# Import job storage
from job_storage import get_job_storage

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimExtractor
from services.factcheck import FactChecker
from services.export import PDFExporter

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
Config.validate()

# Initialize services
transcript_processor = TranscriptProcessor()
claim_extractor = ClaimExtractor()
fact_checker = FactChecker()
pdf_exporter = PDFExporter()

# Get job storage
job_storage = get_job_storage()

# File upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start analysis of transcript"""
    try:
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job
        job_data = {
            'id': job_id,
            'status': 'processing',
            'progress': 0,
            'created_at': datetime.now().isoformat()
        }
        
        # Handle different input types
        if request.content_type and 'multipart/form-data' in request.content_type:
            # File upload
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            # Validate file extension
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
            # Save file
            filename = secure_filename(f"{job_id}_{file.filename}")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Process file based on type
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if filename.endswith('.srt'):
                result = transcript_processor.parse_srt(content)
            elif filename.endswith('.vtt'):
                result = transcript_processor.parse_vtt(content)
            else:
                result = transcript_processor.parse_text(content)
            
            if not result['success']:
                return jsonify({'success': False, 'error': result.get('error', 'Failed to parse file')}), 400
            
            transcript = result['transcript']
            source = f"File: {file.filename}"
            
            # Clean up file
            os.remove(filepath)
            
        else:
            # JSON input
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            input_type = data.get('type')
            
            if input_type == 'text':
                transcript = data.get('content', '').strip()
                if not transcript:
                    return jsonify({'success': False, 'error': 'No transcript text provided'}), 400
                source = "Direct Input"
                
            elif input_type == 'youtube':
                url = data.get('url', '').strip()
                if not url:
                    return jsonify({'success': False, 'error': 'No YouTube URL provided'}), 400
                
                result = transcript_processor.parse_youtube(url)
                if not result['success']:
                    return jsonify({'success': False, 'error': result.get('error', 'Failed to extract YouTube transcript')}), 400
                
                transcript = result['transcript']
                source = f"YouTube: {result.get('title', url)}"
                
            else:
                return jsonify({'success': False, 'error': 'Invalid input type'}), 400
        
        # Validate transcript length
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({'success': False, 'error': f'Transcript too long. Maximum {Config.MAX_TRANSCRIPT_LENGTH} characters allowed.'}), 400
        
        # Store job
        job_data['transcript'] = transcript
        job_data['source'] = source
        job_storage.set(job_id, job_data)
        
        # Start processing in background thread
        thread = threading.Thread(target=process_transcript, args=(job_id, transcript, source))
        thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Analysis started'
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'job_id': job_id,
        'status': job_data.get('status', 'unknown'),
        'progress': job_data.get('progress', 0),
        'error': job_data.get('error')
    })

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    if job_data.get('status') != 'complete':
        return jsonify({'success': False, 'error': 'Analysis not complete'}), 400
    
    results = job_data.get('results', {})
    return jsonify({
        'success': True,
        'results': results
    })

@app.route('/api/export/<job_id>', methods=['POST'])
def export_results(job_id):
    """Export results in various formats"""
    try:
        data = request.get_json()
        format_type = data.get('format', 'json')
        
        job_data = job_storage.get(job_id)
        if not job_data or job_data.get('status') != 'complete':
            return jsonify({'success': False, 'error': 'Results not available'}), 404
        
        results = job_data.get('results', {})
        
        # Generate export filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"factcheck_{timestamp}"
        
        if format_type == 'json':
            filename = f"{base_filename}.json"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
                
        elif format_type == 'txt':
            filename = f"{base_filename}.txt"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'w') as f:
                f.write(generate_text_report(results))
                
        elif format_type == 'pdf':
            filename = f"{base_filename}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            pdf_exporter.generate_pdf(results, filepath)
            
        else:
            return jsonify({'success': False, 'error': 'Invalid format'}), 400
        
        # Return download URL
        return jsonify({
            'success': True,
            'download_url': f'/download/{filename}'
        })
        
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download exported file"""
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def process_transcript(job_id, transcript, source):
    """Process transcript through the fact-checking pipeline"""
    try:
        # Ensure job exists
        if not job_storage.exists(job_id):
            logger.error(f"Job {job_id} not found in job storage")
            return
        
        # Clean transcript
        job_storage.update(job_id, {'progress': 20})
        cleaned_transcript = transcript_processor.clean_transcript(transcript)
        
        # Identify speakers and topics
        job_storage.update(job_id, {'progress': 30})
        speakers, topics = claim_extractor.identify_speakers(transcript)
        
        # Log speaker identification results properly
        if speakers:
            logger.info(f"Job {job_id}: Identified speakers: {speakers[:5]}")  # Show first 5
        else:
            logger.info(f"Job {job_id}: No specific speakers identified")
        
        if topics:
            logger.info(f"Job {job_id}: Key topics: {topics}")
        
        # Extract claims
        job_storage.update(job_id, {'progress': 40})
        claims = claim_extractor.extract_claims(cleaned_transcript)
        logger.info(f"Job {job_id}: Extracted {len(claims)} claims")
        
        # Prioritize and filter claims
        job_storage.update(job_id, {'progress': 50})
        verified_claims = claim_extractor.filter_verifiable(claims)
        prioritized_claims = claim_extractor.prioritize_claims(verified_claims)
        logger.info(f"Job {job_id}: Checking {len(prioritized_claims)} prioritized claims")
        
        # Ensure we have strings, not dictionaries
        if prioritized_claims and isinstance(prioritized_claims[0], dict):
            logger.warning("Claims are dictionaries, extracting text")
            prioritized_claims = [claim['text'] if isinstance(claim, dict) else claim for claim in prioritized_claims]
        
        # Fact check claims
        job_storage.update(job_id, {'progress': 70})
        fact_check_results = []
        
        # Use batch_check but with error handling for individual claims
        claims_to_check = prioritized_claims[:Config.MAX_CLAIMS_PER_TRANSCRIPT]
        
        for i in range(0, len(claims_to_check), Config.FACT_CHECK_BATCH_SIZE):
            batch = claims_to_check[i:i + Config.FACT_CHECK_BATCH_SIZE]
            try:
                batch_results = fact_checker.batch_check(batch)
                fact_check_results.extend(batch_results)
                # Update progress
                progress = 70 + int((len(fact_check_results) / len(claims_to_check)) * 20)
                job_storage.update(job_id, {'progress': progress})
            except Exception as e:
                logger.error(f"Error checking batch starting at {i}: {str(e)}")
                # Add unverified results for failed batch
                for claim in batch:
                    fact_check_results.append({
                        'claim': claim,
                        'verdict': 'unverified',
                        'confidence': 0,
                        'explanation': 'Error during fact-checking',
                        'publisher': 'Error',
                        'url': '',
                        'sources': []
                    })
        
        # Calculate overall credibility
        job_storage.update(job_id, {'progress': 90})
        credibility_score = fact_checker.calculate_credibility(fact_check_results)
        
        # Generate enhanced summary with speaker/topic info
        summary = generate_summary(fact_check_results, credibility_score)
        if speakers:
            summary += f" Main speakers identified: {', '.join(speakers[:3])}."
        if topics:
            summary += f" Key topics: {', '.join(topics)}."
        
        # Compile results
        results = {
            'source': source,
            'transcript_length': len(transcript),
            'word_count': len(transcript.split()),
            'speakers': speakers[:10] if speakers else [],  # Limit to top 10
            'topics': topics,
            'total_claims': len(claims),
            'verified_claims': len(verified_claims),
            'checked_claims': len(fact_check_results),
            'credibility_score': credibility_score,
            'credibility_label': get_credibility_label(credibility_score),
            'fact_checks': fact_check_results,
            'summary': summary,
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Add analysis notes if no API keys
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            results['analysis_notes'] = [
                "Running in demo mode - no fact-checking APIs configured",
                "Results shown are simulated for demonstration purposes",
                "Configure API keys in .env file for real fact-checking"
            ]
        
        # Complete job
        job_storage.update(job_id, {
            'progress': 100,
            'status': 'complete',
            'results': results
        })
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        job_storage.update(job_id, {
            'status': 'error',
            'error': str(e)
        })

def generate_summary(fact_checks, credibility_score):
    """Generate a summary of the fact check results"""
    total = len(fact_checks)
    if total == 0:
        return "No factual claims were identified in this transcript."
    
    true_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['true', 'mostly_true'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict') in ['false', 'mostly_false'])
    mixed_count = sum(1 for fc in fact_checks if fc.get('verdict') == 'mixed')
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict') == 'unverified')
    
    summary = f"Analysis complete: {total} claims fact-checked. "
    
    if credibility_score >= 75:
        summary += f"Overall credibility is HIGH ({credibility_score}%). "
    elif credibility_score >= 50:
        summary += f"Overall credibility is MODERATE ({credibility_score}%). "
    elif credibility_score >= 25:
        summary += f"Overall credibility is LOW ({credibility_score}%). "
    else:
        summary += f"Overall credibility is VERY LOW ({credibility_score}%). "
    
    summary += f"Found {true_count} true, {false_count} false, {mixed_count} mixed, and {unverified_count} unverified claims."
    
    return summary

def get_credibility_label(score):
    """Get label for credibility score"""
    if score >= 75:
        return "High Credibility"
    elif score >= 50:
        return "Moderate Credibility"
    elif score >= 25:
        return "Low Credibility"
    else:
        return "Very Low Credibility"

def generate_text_report(results):
    """Generate a text report of the results"""
    report = []
    report.append("TRANSCRIPT FACT CHECK REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Source: {results.get('source', 'Unknown')}")
    report.append(f"Credibility Score: {results.get('credibility_score', 0)}% ({results.get('credibility_label', 'Unknown')})")
    report.append("")
    
    if results.get('speakers'):
        report.append(f"Speakers: {', '.join(results['speakers'][:5])}")
    
    if results.get('topics'):
        report.append(f"Topics: {', '.join(results['topics'])}")
    
    report.append("")
    report.append("SUMMARY")
    report.append("-" * 50)
    report.append(results.get('summary', 'No summary available'))
    report.append("")
    
    report.append("DETAILED FACT CHECKS")
    report.append("-" * 50)
    
    for i, fc in enumerate(results.get('fact_checks', []), 1):
        report.append(f"\n{i}. CLAIM: {fc.get('claim', 'No claim text')}")
        report.append(f"   VERDICT: {fc.get('verdict', 'unverified').upper()}")
        if fc.get('confidence'):
            report.append(f"   CONFIDENCE: {fc.get('confidence', 0)}%")
        report.append(f"   EXPLANATION: {fc.get('explanation', 'No explanation available')}")
        if fc.get('sources'):
            report.append(f"   SOURCES: {', '.join(fc.get('sources', []))}")
    
    return "\n".join(report)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('index.html'), 200  # Let frontend handle routing

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

# Entry point for development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)

# IMPORTANT: The Flask app variable MUST be named 'app' for Gunicorn to find it
# This is what Gunicorn looks for with the command: gunicorn app:app
