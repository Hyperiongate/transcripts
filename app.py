"""
Transcript Fact Checker - Main Flask Application
AI-powered fact-checking for transcripts and speeches
"""
import os
import uuid
import logging
import traceback
import time
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
job_storage = get_job_storage()

# File upload handling
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start transcript analysis - handles text, file, and YouTube inputs"""
    try:
        job_id = str(uuid.uuid4())
        logger.info(f"Starting analysis job: {job_id}")
        
        # Handle different input types based on content type
        if request.content_type and 'multipart/form-data' in request.content_type:
            # File upload
            input_type = request.form.get('type', 'file')
        else:
            # JSON input (text or YouTube)
            data = request.get_json()
            input_type = data.get('type') if data else None
        
        logger.info(f"Input type: {input_type}")
        
        if input_type == 'text':
            # Text input
            data = request.get_json()
            if not data or not data.get('content'):
                return jsonify({
                    'success': False,
                    'error': 'No text content provided'
                }), 400
                
            transcript = data.get('content', '')
            source = 'Direct Text Input'
            logger.info(f"Processing text input, length: {len(transcript)}")
            
        elif input_type == 'youtube':
            # YouTube URL
            data = request.get_json()
            if not data or not data.get('url'):
                return jsonify({
                    'success': False,
                    'error': 'No YouTube URL provided'
                }), 400
                
            url = data.get('url', '').strip()
            logger.info(f"Processing YouTube URL: {url}")
            
            # Validate YouTube URL format
            if not url:
                return jsonify({
                    'success': False,
                    'error': 'Empty YouTube URL'
                }), 400
            
            if 'youtube.com' not in url and 'youtu.be' not in url:
                return jsonify({
                    'success': False,
                    'error': 'Invalid YouTube URL. Please provide a valid YouTube video URL.'
                }), 400
            
            # Extract transcript from YouTube
            try:
                result = transcript_processor.parse_youtube(url)
                logger.info(f"YouTube extraction result: {result}")
                
                if not result['success']:
                    error_msg = result.get('error', 'Failed to extract YouTube transcript')
                    logger.error(f"YouTube extraction failed: {error_msg}")
                    
                    # Provide more helpful error messages
                    if 'Transcripts are disabled' in error_msg:
                        error_msg = 'This video has transcripts/captions disabled. Please try a different video.'
                    elif 'No transcript available' in error_msg:
                        error_msg = 'No transcript/captions found for this video. Please try a video with captions enabled.'
                    elif 'Video is unavailable' in error_msg:
                        error_msg = 'This video is unavailable or private. Please try a public video.'
                    elif 'Invalid YouTube URL' in error_msg:
                        error_msg = 'Could not extract video ID from URL. Please check the URL format.'
                    
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 400
                
                transcript = result.get('transcript', '')
                video_title = result.get('title', 'Unknown Video')
                video_id = result.get('video_id', '')
                duration = result.get('duration', 0)
                
                # Check duration limit
                if duration > Config.YOUTUBE_MAX_DURATION:
                    return jsonify({
                        'success': False,
                        'error': f'Video is too long. Maximum duration is {Config.YOUTUBE_MAX_DURATION // 60} minutes.'
                    }), 400
                
                source = f"YouTube: {video_title} (ID: {video_id})"
                logger.info(f"Successfully extracted YouTube transcript: {len(transcript)} characters")
                
            except Exception as e:
                logger.error(f"YouTube extraction exception: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'error': f'Failed to extract YouTube transcript: {str(e)}'
                }), 500
            
        elif input_type == 'file':
            # File upload
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type. Allowed types: TXT, SRT, VTT'}), 400
            
            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > Config.MAX_FILE_SIZE:
                return jsonify({'success': False, 'error': f'File too large. Maximum size is {Config.MAX_FILE_SIZE // (1024*1024)}MB'}), 400
            
            # Save file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
            file.save(filepath)
            
            try:
                # Process file
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                logger.info(f"Processing file: {filename}, size: {len(content)} chars")
                
                if filename.endswith('.srt'):
                    result = transcript_processor.parse_srt(content)
                elif filename.endswith('.vtt'):
                    result = transcript_processor.parse_vtt(content)
                else:
                    result = transcript_processor.parse_text(content)
                
                if not result['success']:
                    return jsonify({
                        'success': False,
                        'error': result.get('error', 'Failed to parse file')
                    }), 400
                
                transcript = result['transcript']
                source = f"File: {filename}"
                
            finally:
                # Always clean up the file
                if os.path.exists(filepath):
                    os.remove(filepath)
            
        else:
            return jsonify({'success': False, 'error': 'Invalid input type. Must be text, youtube, or file.'}), 400
        
        # Validate transcript content
        if not transcript or len(transcript.strip()) < 50:
            return jsonify({
                'success': False,
                'error': 'Content too short. Please provide at least 50 characters of text.'
            }), 400
        
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({
                'success': False,
                'error': f'Content too long. Maximum length is {Config.MAX_TRANSCRIPT_LENGTH:,} characters.'
            }), 400
        
        # Create job
        job_data = {
            'id': job_id,
            'status': 'processing',
            'progress': 0,
            'source': source,
            'input_type': input_type,
            'created_at': datetime.now().isoformat()
        }
        job_storage.set(job_id, job_data)
        
        logger.info(f"Created job {job_id} for {input_type} input: {source}")
        
        # Start processing in background
        thread = Thread(
            target=process_transcript, 
            args=(job_id, transcript, source),
            name=f"process_{job_id}"
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Analysis started',
            'source': source
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

def generate_conversational_summary(fact_check_results, credibility_score, speaker, speaker_context, speaker_history):
    """Generate conversational summary with full speaker context"""
    if not fact_check_results:
        return "No claims were found to fact-check in this transcript."
    
    # Start with speaker context if available
    summary = ""
    
    if speaker and speaker_context:
        if speaker_context.get('criminal_record'):
            summary += f"IMPORTANT CONTEXT: {speaker} is a {speaker_context['criminal_record']}. "
        
        if speaker_context.get('fraud_history'):
            summary += f"{speaker_context['fraud_history']}. "
        
        if speaker_context.get('fact_check_history'):
            summary += f"Historical fact-checking shows: {speaker_context['fact_check_history']}. "
        
        summary += "\n\n"
    
    # Analyze current transcript
    summary += f"In this transcript, we analyzed {len(fact_check_results)} claims. "
    
    # Count verdict types
    verdict_counts = defaultdict(int)
    for result in fact_check_results:
        verdict = result.get('verdict', 'unverified')
        verdict_counts[verdict] += 1
    
    # Overall assessment
    if credibility_score >= 80:
        summary += f"The credibility score is {credibility_score}%, indicating high accuracy. "
    elif credibility_score >= 60:
        summary += f"The credibility score is {credibility_score}%, showing moderate accuracy with some issues. "
    elif credibility_score >= 40:
        summary += f"The credibility score is {credibility_score}%, revealing significant credibility problems. "
    else:
        summary += f"The credibility score is only {credibility_score}%, indicating severe credibility issues. "
    
    # Specific findings
    if verdict_counts['false'] + verdict_counts['mostly_false'] > 0:
        summary += f"Found {verdict_counts['false'] + verdict_counts['mostly_false']} false or mostly false claims. "
    
    if verdict_counts['deceptive'] > 0:
        summary += f"ALERT: {verdict_counts['deceptive']} claims appear deliberately deceptive. "
    
    if verdict_counts['lacks_context'] > 0:
        summary += f"{verdict_counts['lacks_context']} claims omit critical context. "
    
    # Pattern analysis
    if verdict_counts['deceptive'] >= 3:
        summary += "\n\n⚠️ PATTERN DETECTED: Multiple deliberately deceptive statements suggest intentional misrepresentation."
    elif verdict_counts['false'] + verdict_counts['mostly_false'] >= 5:
        summary += "\n\n⚠️ PATTERN DETECTED: High number of false claims indicates unreliable information."
    
    # Compare to speaker's history if available
    if speaker_history and speaker_history.get('total_analyses', 0) > 1:
        avg_cred = speaker_history['average_credibility']
        if credibility_score < avg_cred - 15:
            summary += f"\n\nNOTE: This performance ({credibility_score}%) is significantly worse than {speaker}'s average ({avg_cred:.0f}%)."
        elif credibility_score > avg_cred + 15:
            summary += f"\n\nNOTE: This performance ({credibility_score}%) is better than {speaker}'s average ({avg_cred:.0f}%)."
    
    return summary

def generate_summary(fact_check_results, credibility_score):
    """Generate a human-readable summary of the fact check results"""
    if not fact_check_results:
        return "No claims were found to fact-check in this transcript."
    
    # Count verdict types
    verdict_counts = {
        'true': 0,
        'mostly_true': 0,
        'mixed': 0,
        'misleading': 0,
        'deceptive': 0,
        'lacks_context': 0,
        'unsubstantiated': 0,
        'mostly_false': 0,
        'false': 0,
        'unverified': 0
    }
    
    for result in fact_check_results:
        verdict = result.get('verdict', 'unverified').lower().replace(' ', '_')
        # Handle old 'misleading' verdicts
        if verdict == 'misleading':
            verdict = 'deceptive'
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
        else:
            verdict_counts['unverified'] += 1
    
    # Generate conversational summary
    total_claims = len(fact_check_results)
    true_claims = verdict_counts['true'] + verdict_counts['mostly_true']
    false_claims = verdict_counts['false'] + verdict_counts['mostly_false']
    deceptive_claims = verdict_counts['deceptive'] + verdict_counts['misleading']
    
    # Start with overall assessment
    if credibility_score >= 80:
        summary = f"This transcript shows high credibility with a score of {credibility_score}%. "
    elif credibility_score >= 60:
        summary = f"This transcript shows moderate credibility with a score of {credibility_score}%. "
    elif credibility_score >= 40:
        summary = f"This transcript shows concerning credibility issues with a score of {credibility_score}%. "
    else:
        summary = f"This transcript has serious credibility problems with a score of only {credibility_score}%. "
    
    # Add claim breakdown
    summary += f"Out of {total_claims} fact-checkable claims: "
    
    parts = []
    if true_claims > 0:
        parts.append(f"{true_claims} were verified as true or mostly true")
    if false_claims > 0:
        parts.append(f"{false_claims} were found to be false or mostly false")
    if deceptive_claims > 0:
        parts.append(f"{deceptive_claims} were deliberately deceptive")
    if verdict_counts['lacks_context'] > 0:
        parts.append(f"{verdict_counts['lacks_context']} lacked critical context")
    if verdict_counts['unverified'] > 0:
        parts.append(f"{verdict_counts['unverified']} could not be verified")
    
    if parts:
        summary += ", ".join(parts) + "."
    
    # Add pattern warnings
    if deceptive_claims >= 3:
        summary += " WARNING: This shows a pattern of deliberate misrepresentation."
    elif false_claims >= 3:
        summary += " Multiple false statements suggest unreliable information."
    
    return summary

def get_credibility_label(score):
    """Convert credibility score to label"""
    if score >= 80:
        return "High Credibility"
    elif score >= 60:
        return "Moderate Credibility"
    elif score >= 40:
        return "Low Credibility"
    elif score >= 20:
        return "Very Low Credibility"
    else:
        return "Extremely Low Credibility"

def process_transcript(job_id, transcript, source):
    """Process transcript through the fact-checking pipeline with speaker context"""
    try:
        logger.info(f"Starting transcript processing for job {job_id}")
        
        # Ensure job exists
        if not job_storage.exists(job_id):
            logger.error(f"Job {job_id} not found in job storage")
            return
        
        # Clean transcript
        job_storage.update(job_id, {'progress': 20, 'status': 'processing'})
        cleaned_transcript = transcript_processor.clean_transcript(transcript)
        logger.info(f"Cleaned transcript: {len(cleaned_transcript)} chars")
        
        # Identify speakers and topics
        job_storage.update(job_id, {'progress': 30, 'status': 'processing'})
        speakers, topics = claim_extractor.identify_speakers(transcript)
        logger.info(f"Identified {len(speakers)} speakers and {len(topics)} topics")
        
        # Extract main speaker for history tracking
        main_speaker = None
        speaker_context = {}
        
        if speakers:
            # Use speaker_tracker to extract speaker, fallback to first identified speaker
            extracted_speaker = speaker_tracker.extract_speaker(source, transcript)
            main_speaker = extracted_speaker if extracted_speaker else speakers[0]
            logger.info(f"Main speaker identified as {main_speaker}")
            
            # Get speaker background and context
            speaker_context = fact_checker.get_speaker_context(main_speaker)
            logger.info(f"Speaker context retrieved: {speaker_context.get('credibility_notes', 'None')}")
        
        # Extract claims with full context
        job_storage.update(job_id, {'progress': 40, 'status': 'processing'})
        claims = claim_extractor.extract_claims(cleaned_transcript)
        logger.info(f"Extracted {len(claims)} claims")
        
        # Add context resolution
        for claim in claims:
            resolved_text, context_info = context_resolver.resolve_context(claim['text'])
            claim['resolved_text'] = resolved_text
            claim['context_info'] = context_info
            claim['full_text'] = claim['text']
            context_resolver.add_claim_to_context(claim['text'])
        
        # Prioritize and filter claims
        job_storage.update(job_id, {'progress': 50, 'status': 'processing'})
        verified_claims = claim_extractor.filter_verifiable(claims)
        prioritized_claims = claim_extractor.prioritize_claims(verified_claims)
        logger.info(f"Checking {len(prioritized_claims)} prioritized claims")
        
        # Prepare claims for checking
        claims_to_check = []
        for claim in prioritized_claims[:Config.MAX_CLAIMS_PER_TRANSCRIPT]:
            if isinstance(claim, dict):
                claims_to_check.append({
                    'text': claim.get('resolved_text', claim['text']),
                    'full_context': claim.get('full_text', claim['text']),
                    'original': claim
                })
            else:
                claims_to_check.append({
                    'text': claim,
                    'full_context': claim,
                    'original': {'text': claim}
                })
        
        # Fact check claims with comprehensive checking
        job_storage.update(job_id, {'progress': 70, 'status': 'fact_checking'})
        fact_check_results = []
        
        # Set a maximum time for fact-checking (60 seconds total)
        batch_timeout = 60  # Total timeout for all fact-checking
        start_time = time.time()
        
        for i in range(0, len(claims_to_check), Config.FACT_CHECK_BATCH_SIZE):
            # Check if we've exceeded our time budget
            elapsed_time = time.time() - start_time
            if elapsed_time > batch_timeout:
                logger.warning(f"Fact-checking timeout reached after {elapsed_time:.1f}s and {len(fact_check_results)} claims")
                # Add demo results for remaining claims
                for claim_data in claims_to_check[i:]:
                    demo_result = fact_checker._create_demo_result(claim_data['text'])
                    demo_result['full_context'] = claim_data['full_context']
                    fact_check_results.append(demo_result)
                break
            
            batch = claims_to_check[i:i + Config.FACT_CHECK_BATCH_SIZE]
            try:
                # Use the fast batch checking with timeout protection
                batch_texts = [c['text'] for c in batch]
                batch_results = fact_checker.batch_check(batch_texts)
                
                # Add full context back to results
                for j, result in enumerate(batch_results):
                    result['full_context'] = batch[j]['full_context']
                    original = batch[j]['original']
                    if original.get('context_info', {}).get('resolved'):
                        result['context_note'] = f"Context resolved: {original['context_info'].get('resolved_claim', '')}"
                
                fact_check_results.extend(batch_results)
                
                # Update progress
                progress = 70 + int((len(fact_check_results) / len(claims_to_check)) * 20)
                job_storage.update(job_id, {'progress': progress})
                
            except Exception as e:
                logger.error(f"Error checking batch starting at {i}: {str(e)}")
                for claim_data in batch:
                    demo_result = fact_checker._create_demo_result(claim_data['text'])
                    demo_result['full_context'] = claim_data['full_context']
                    fact_check_results.append(demo_result)
        
        # Calculate overall credibility
        job_storage.update(job_id, {'progress': 90, 'status': 'generating_report'})
        credibility_score = fact_checker.calculate_credibility(fact_check_results)
        
        # Generate enhanced conversational summary with speaker context
        summary = generate_summary(fact_check_results, credibility_score)
        conversational_summary = generate_conversational_summary(
            fact_check_results, 
            credibility_score, 
            main_speaker, 
            speaker_context,
            speaker_tracker.get_speaker_summary(main_speaker) if main_speaker else None
        )
        
        # Get speaker history if available
        speaker_history = None
        if main_speaker:
            speaker_history = speaker_tracker.get_speaker_summary(main_speaker)
        
        # Add note about API availability if in demo mode
        analysis_notes = []
        if not Config.get_active_apis():
            analysis_notes.append("Running in demo mode - results are simulated. Configure API keys for real fact-checking.")
        
        # Compile results with speaker context
        results = {
            'source': source,
            'speaker': main_speaker,
            'speaker_context': speaker_context,  # Criminal record, fraud history, etc.
            'speaker_history': speaker_history,   # Our tracking history
            'transcript_length': len(transcript),
            'word_count': len(transcript.split()),
            'speakers': speakers[:10] if speakers else [],
            'topics': topics,
            'total_claims': len(claims),
            'verified_claims': len(verified_claims),
            'checked_claims': len(fact_check_results),
            'credibility_score': credibility_score,
            'credibility_label': get_credibility_label(credibility_score),
            'fact_checks': fact_check_results,
            'summary': summary,
            'conversational_summary': conversational_summary,
            'analysis_notes': analysis_notes,
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Track this analysis for the speaker
        if main_speaker:
            speaker_tracker.add_analysis(main_speaker, results)
        
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

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'job_id': job_id,
        'status': job_data.get('status'),
        'progress': job_data.get('progress', 0),
        'error': job_data.get('error'),
        'source': job_data.get('source')
    })

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get job results"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    if job_data.get('status') != 'complete':
        return jsonify({
            'success': False,
            'error': f'Job not complete. Current status: {job_data.get("status", "unknown")}'
        }), 400
    
    return jsonify({
        'success': True,
        'results': job_data.get('results', {})
    })

@app.route('/api/export/<job_id>', methods=['POST'])
def export_results(job_id):
    """Export results in various formats"""
    try:
        job_data = job_storage.get(job_id)
        
        if not job_data or job_data.get('status') != 'complete':
            return jsonify({'success': False, 'error': 'Results not available'}), 404
        
        results = job_data.get('results', {})
        format_type = request.json.get('format', 'pdf')
        
        if format_type == 'pdf':
            output_path = f"exports/{job_id}.pdf"
            os.makedirs('exports', exist_ok=True)
            
            # Generate enhanced PDF with all information
            success = pdf_exporter.generate_pdf(results, output_path)
            
            if success:
                # Send file then delete it
                def remove_file(response):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                    return response
                
                return send_file(
                    output_path,
                    as_attachment=True,
                    download_name=f"fact-check-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf",
                    mimetype='application/pdf'
                )
            else:
                return jsonify({'success': False, 'error': 'PDF generation failed'}), 500
                
        elif format_type == 'json':
            # Return JSON download
            return jsonify(results)
            
        elif format_type == 'txt':
            # Generate text report
            report = generate_text_report(results)
            return report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact-check-report-{job_id}.txt'
            }
            
        else:
            return jsonify({'success': False, 'error': 'Invalid format'}), 400
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_text_report(results):
    """Generate a text report from results"""
    report = []
    report.append("TRANSCRIPT FACT CHECK REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    report.append(f"Source: {results.get('source', 'Unknown')}")
    
    if results.get('speaker'):
        report.append(f"Speaker: {results['speaker']}")
    
    # Add speaker context if available
    if results.get('speaker_context'):
        context = results['speaker_context']
        report.append("")
        report.append("SPEAKER BACKGROUND")
        report.append("-" * 50)
        if context.get('criminal_record'):
            report.append(f"Criminal Record: {context['criminal_record']}")
        if context.get('fraud_history'):
            report.append(f"Fraud History: {context['fraud_history']}")
        if context.get('fact_check_history'):
            report.append(f"Fact Check History: {context['fact_check_history']}")
        if context.get('credibility_notes'):
            report.append(f"Notes: {context['credibility_notes']}")
        report.append("")
    
    report.append(f"Credibility Score: {results.get('credibility_score', 0)}% ({results.get('credibility_label', 'Unknown')})")
    report.append("")
    
    # Add conversational summary
    if results.get('conversational_summary'):
        report.append("SUMMARY")
        report.append("-" * 50)
        report.append(results['conversational_summary'])
        report.append("")
    
    # Add speaker history if available
    if results.get('speaker_history'):
        history = results['speaker_history']
        report.append("SPEAKER HISTORY")
        report.append("-" * 50)
        report.append(f"Previous analyses: {history['total_analyses']}")
        report.append(f"Average credibility: {history['average_credibility']:.0f}%")
        if history['patterns']:
            report.append(f"Patterns: {', '.join(history['patterns'])}")
        report.append("")
    
    report.append("STATISTICS")
    report.append("-" * 50)
    report.append(f"Total Claims: {results.get('checked_claims', 0)}")
    
    # Count verdicts
    verdict_counts = {}
    for check in results.get('fact_checks', []):
        verdict = check.get('verdict', 'unverified')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    
    for verdict, count in verdict_counts.items():
        report.append(f"{verdict.replace('_', ' ').title()}: {count}")
    report.append("")
    
    report.append("DETAILED FACT CHECKS")
    report.append("-" * 50)
    
    for i, check in enumerate(results.get('fact_checks', []), 1):
        report.append(f"\nClaim {i}:")
        # Show full context
        if check.get('full_context'):
            report.append(f"Full statement: {check['full_context']}")
        else:
            report.append(f"Claim: {check.get('claim', 'N/A')}")
        report.append(f"Verdict: {check.get('verdict', 'unverified').upper()}")
        
        if check.get('confidence'):
            report.append(f"Confidence: {check['confidence']}%")
        
        report.append(f"Explanation: {check.get('explanation', 'No explanation available')}")
        
        if check.get('sources'):
            report.append(f"Sources: {', '.join(check['sources'])}")
        
        report.append("")
    
    return "\n".join(report)

@app.route('/api/test/youtube', methods=['GET'])
def test_youtube():
    """Test endpoint to verify YouTube functionality"""
    try:
        # Test with a known public video
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = transcript_processor.parse_youtube(test_url)
        
        return jsonify({
            'success': True,
            'test_url': test_url,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    logger.info(f"Starting app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
