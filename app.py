"""
Transcript Fact Checker - Main Flask Application
AI-powered fact-checking for transcripts and speeches
"""
import os
import uuid
import logging
import traceback
from datetime import datetime
from threading import Thread
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, send_file
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
from services.context_resolver import ContextResolver
from services.speaker_history import SpeakerHistoryTracker
from services.temporal_context import TemporalContextHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
pdf_exporter = PDFExporter()
context_resolver = ContextResolver()
speaker_tracker = SpeakerHistoryTracker()
temporal_handler = TemporalContextHandler()
job_storage = get_job_storage()

# File upload handling
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def analyze_patterns(fact_checks):
    """Analyze patterns in fact checks to detect intentional deception"""
    patterns = {
        'false_claims': 0,
        'misleading_claims': 0,
        'intentionally_deceptive': 0,
        'exaggerations': 0,
        'opinion_as_fact': 0,
        'total_claims': len(fact_checks),
        'deception_pattern': False,
        'concerning_claims': []
    }
    
    for check in fact_checks:
        verdict = check.get('verdict', 'unverified').lower()
        
        if verdict == 'false':
            patterns['false_claims'] += 1
            patterns['concerning_claims'].append(check.get('claim', ''))
        elif verdict == 'misleading':
            patterns['misleading_claims'] += 1
            patterns['concerning_claims'].append(check.get('claim', ''))
        elif verdict == 'intentionally_deceptive':
            patterns['intentionally_deceptive'] += 1
            patterns['concerning_claims'].append(check.get('claim', ''))
        elif verdict == 'exaggeration':
            patterns['exaggerations'] += 1
        elif verdict == 'opinion':
            patterns['opinion_as_fact'] += 1
    
    # Detect pattern of deception
    deceptive_count = patterns['false_claims'] + patterns['misleading_claims'] + patterns['intentionally_deceptive']
    if deceptive_count >= 3 or patterns['intentionally_deceptive'] >= 1:
        patterns['deception_pattern'] = True
    
    patterns['deceptive_percentage'] = (deceptive_count / patterns['total_claims'] * 100) if patterns['total_claims'] > 0 else 0
    
    return patterns

def generate_enhanced_summary(results):
    """Generate an enhanced conversational summary with all context"""
    summary = []
    
    # Speaker context
    speakers = results.get('speakers', {})
    if speakers:
        summary.append("SPEAKER BACKGROUND")
        summary.append("-" * 50)
        for speaker, context in speakers.items():
            if context.get('criminal_record') or context.get('fraud_history'):
                summary.append(f"\n⚠️ WARNING: {speaker} has a concerning background:")
                if context.get('criminal_record'):
                    summary.append(f"Criminal Record: {context['criminal_record']}")
                if context.get('fraud_history'):
                    summary.append(f"Fraud History: {context['fraud_history']}")
        summary.append("")
    
    # Pattern analysis
    fact_checks = results.get('fact_checks', [])
    patterns = analyze_patterns(fact_checks)
    
    summary.append("CREDIBILITY ASSESSMENT")
    summary.append("-" * 50)
    
    if patterns['deception_pattern']:
        summary.append("🚨 PATTERN OF DECEPTION DETECTED")
        summary.append(f"This transcript contains {patterns['false_claims']} false claims, "
                      f"{patterns['misleading_claims']} misleading claims, and "
                      f"{patterns['intentionally_deceptive']} intentionally deceptive statements.")
        summary.append("\nThis appears to be a deliberate pattern of misinformation.")
    else:
        summary.append(f"✓ Analysis of {patterns['total_claims']} claims:")
        summary.append(f"  - True/Mostly True: {patterns['total_claims'] - patterns['false_claims'] - patterns['misleading_claims'] - patterns['exaggerations']}")
        summary.append(f"  - False/Misleading: {patterns['false_claims'] + patterns['misleading_claims']}")
        summary.append(f"  - Exaggerations: {patterns['exaggerations']}")
    
    # Most concerning claims
    if patterns['concerning_claims']:
        summary.append("\nMOST CONCERNING FALSE CLAIMS:")
        for i, claim in enumerate(patterns['concerning_claims'][:5], 1):
            summary.append(f"{i}. {claim}")
    
    # Overall verdict
    summary.append("\nOVERALL VERDICT:")
    if patterns['deceptive_percentage'] >= 50:
        summary.append("❌ HIGHLY UNRELIABLE - Majority of verifiable claims are false or misleading")
    elif patterns['deceptive_percentage'] >= 25:
        summary.append("⚠️ QUESTIONABLE - Significant number of false or misleading claims")
    elif patterns['deceptive_percentage'] >= 10:
        summary.append("⚡ MOSTLY ACCURATE - Some false claims but generally reliable")
    else:
        summary.append("✅ RELIABLE - Very few or no false claims detected")
    
    # AI usage note
    if any(check.get('ai_analysis_used') for check in fact_checks):
        summary.append("\n💡 AI-powered analysis was used to enhance accuracy and context understanding.")
    
    return "\n".join(summary)

def process_transcript(transcript_text, source_type='text', job_id=None, speech_date=None):
    """Process transcript with full context and enhanced fact-checking"""
    try:
        logger.info(f"Processing transcript for job {job_id}")
        
        # Update job status
        if job_id:
            job_storage.update_job(job_id, {
                'status': 'processing',
                'stage': 'extracting_claims',
                'checked_claims': 0
            })
        
        # Set temporal context if speech date provided
        if speech_date:
            temporal_handler.set_speech_date(speech_date)
        
        # Extract metadata and resolve speakers
        metadata = transcript_processor.extract_metadata(transcript_text)
        speakers = context_resolver.resolve_speakers(metadata.get('speakers', []))
        
        # Extract claims with enhanced AI
        claims = claim_extractor.extract_claims_enhanced(transcript_text, use_ai=True)
        total_claims = len(claims)
        
        logger.info(f"Extracted {total_claims} claims")
        
        # Initialize results
        results = {
            'job_id': job_id,
            'source_type': source_type,
            'metadata': metadata,
            'speakers': {},
            'fact_checks': [],
            'summary': '',
            'enhanced_summary': '',
            'checked_claims': 0,
            'total_claims': total_claims,
            'patterns': {}
        }
        
        # Get speaker context
        for speaker in speakers:
            context = fact_checker.get_speaker_context(speaker)
            results['speakers'][speaker] = context
            speaker_tracker.update_speaker_record(speaker, context)
        
        # Fact check each claim
        for i, claim in enumerate(claims):
            if job_id:
                job_storage.update_job(job_id, {
                    'checked_claims': i + 1,
                    'progress': int((i + 1) / total_claims * 100)
                })
            
            # Use comprehensive checking
            try:
                fact_check = fact_checker.check_claim_comprehensive(
                    claim,
                    context={
                        'speakers': speakers,
                        'metadata': metadata,
                        'speech_date': speech_date,
                        'full_transcript': transcript_text
                    }
                )
            except:
                # Fallback to regular checking
                fact_check = fact_checker.check_claim(claim)
            
            # Add temporal context resolution
            if speech_date and temporal_handler:
                fact_check = temporal_handler.resolve_temporal_references(
                    fact_check,
                    speech_date
                )
            
            results['fact_checks'].append(fact_check)
        
        # Analyze patterns
        results['patterns'] = analyze_patterns(results['fact_checks'])
        
        # Generate summaries
        results['summary'] = fact_checker.generate_summary(results['fact_checks'])
        results['enhanced_summary'] = generate_enhanced_summary(results)
        results['checked_claims'] = len(results['fact_checks'])
        
        # Update speaker history
        for speaker in speakers:
            speaker_tracker.add_fact_check_results(
                speaker,
                results['fact_checks'],
                results['patterns']
            )
        
        # Store results
        if job_id:
            job_storage.store_results(job_id, results)
            job_storage.update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.utcnow()
            })
        
        logger.info(f"Completed processing for job {job_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error processing transcript: {str(e)}")
        logger.error(traceback.format_exc())
        
        if job_id:
            job_storage.update_job(job_id, {
                'status': 'failed',
                'error': str(e)
            })
        
        raise

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze transcript endpoint"""
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Get transcript data
        transcript_text = None
        source_type = request.form.get('source_type', 'text')
        speech_date = request.form.get('speech_date')
        
        if source_type == 'file':
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
                file.save(filepath)
                
                # Process file based on type
                transcript_text = transcript_processor.process_file(filepath)
            else:
                return jsonify({'error': 'Invalid file type'}), 400
        
        elif source_type == 'youtube':
            youtube_url = request.form.get('youtube_url')
            if not youtube_url:
                return jsonify({'error': 'No YouTube URL provided'}), 400
            
            transcript_text = transcript_processor.process_youtube(youtube_url)
        
        else:  # text
            transcript_text = request.form.get('transcript')
            if not transcript_text:
                return jsonify({'error': 'No transcript provided'}), 400
        
        # Create job
        job_storage.create_job(job_id, {
            'source_type': source_type,
            'speech_date': speech_date,
            'status': 'queued'
        })
        
        # Process in background
        thread = Thread(
            target=process_transcript,
            args=(transcript_text, source_type, job_id, speech_date)
        )
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Analysis started'
        })
        
    except Exception as e:
        logger.error(f"Error in analyze endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    try:
        job = job_storage.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job)
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    try:
        results = job_storage.get_results(job_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/export/<job_id>/<format>')
def export_results(job_id, format):
    """Export results in various formats"""
    try:
        results = job_storage.get_results(job_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        if format == 'pdf':
            pdf_path = pdf_exporter.export_to_pdf(results)
            return send_file(pdf_path, as_attachment=True, 
                           download_name=f'fact_check_{job_id}.pdf')
        
        elif format == 'json':
            return jsonify(results)
        
        elif format == 'text':
            text_report = generate_text_report(results)
            return text_report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact_check_{job_id}.txt'
            }
        
        else:
            return jsonify({'error': 'Invalid format'}), 400
            
    except Exception as e:
        logger.error(f"Error exporting results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/speakers')
def get_speakers():
    """Get list of known speakers with their history"""
    try:
        speakers = speaker_tracker.get_all_speakers()
        return jsonify(speakers)
    except Exception as e:
        logger.error(f"Error getting speakers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/speaker/<name>')
def get_speaker_details(name):
    """Get detailed information about a specific speaker"""
    try:
        details = speaker_tracker.get_speaker_details(name)
        if not details:
            return jsonify({'error': 'Speaker not found'}), 404
        return jsonify(details)
    except Exception as e:
        logger.error(f"Error getting speaker details: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_text_report(results):
    """Generate a text report from results"""
    report = []
    report.append("FACT CHECK REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Enhanced summary at the top
    report.append("EXECUTIVE SUMMARY")
    report.append("-" * 50)
    report.append(results.get('enhanced_summary', 'No summary available'))
    report.append("")
    
    # Speaker information
    if results.get('speakers'):
        report.append("SPEAKER INFORMATION")
        report.append("-" * 50)
        for speaker, context in results['speakers'].items():
            report.append(f"\n{speaker}:")
            if context.get('criminal_record'):
                report.append(f"  Criminal Record: {context['criminal_record']}")
            if context.get('fraud_history'):
                report.append(f"  Fraud History: {context['fraud_history']}")
            if context.get('fact_check_history'):
                history = context['fact_check_history']
                report.append(f"  Past Fact Checks: {history.get('total_claims', 0)} claims")
                report.append(f"  Average Accuracy: {history.get('accuracy_rate', 0):.1f}%")
        report.append("")
    
    # Pattern analysis
    if results.get('patterns'):
        report.append("PATTERN ANALYSIS")
        report.append("-" * 50)
        patterns = results['patterns']
        if patterns.get('deception_pattern'):
            report.append("⚠️ PATTERN OF DECEPTION DETECTED")
        report.append(f"Total Claims: {patterns.get('total_claims', 0)}")
        report.append(f"False Claims: {patterns.get('false_claims', 0)}")
        report.append(f"Misleading Claims: {patterns.get('misleading_claims', 0)}")
        report.append(f"Intentionally Deceptive: {patterns.get('intentionally_deceptive', 0)}")
        report.append("")
    
    # Detailed fact checks
    report.append("DETAILED FACT CHECKS")
    report.append("-" * 50)
    
    for i, check in enumerate(results.get('fact_checks', []), 1):
        report.append(f"\nClaim {i}:")
        report.append(f"Statement: {check.get('full_context', check.get('claim', 'N/A'))}")
        report.append(f"Verdict: {check.get('verdict', 'unverified').upper()}")
        
        if check.get('confidence'):
            report.append(f"Confidence: {check['confidence']}%")
        
        report.append(f"Explanation: {check.get('explanation', 'No explanation available')}")
        
        if check.get('sources'):
            report.append(f"Sources: {', '.join(check['sources'])}")
        
        if check.get('ai_analysis_used'):
            report.append("✓ AI-enhanced analysis")
        
        report.append("")
    
    return "\n".join(report)

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
