#!/usr/bin/env python3
"""
Enhanced Flask application for Political Transcript Fact Checker
Realistic implementation without false YouTube streaming claims
"""

import os
import logging
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from config import Config

# Import services
from services.claims import ClaimExtractor
from services.comprehensive_factcheck import ComprehensiveFactChecker as FactChecker
from services.export import ExportService
from services.youtube_service import YouTubeService  # New realistic YouTube service
from services.transcript import TranscriptProcessor

# Set up logging
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
config_warnings = Config.validate()
if config_warnings:
    for warning in config_warnings:
        logger.warning(warning)

# Initialize services
claim_extractor = ClaimExtractor(Config)
fact_checker = FactChecker(Config)
export_service = ExportService()
youtube_service = YouTubeService()  # New YouTube service
transcript_processor = TranscriptProcessor()

# In-memory job storage
jobs = {}
job_lock = threading.Lock()

# [VERDICT_CATEGORIES remains the same as in your original]
VERDICT_CATEGORIES = {
    'true': {
        'label': 'True',
        'icon': '✅',
        'color': '#10b981',
        'score': 100,
        'description': 'The claim is accurate and supported by evidence'
    },
    'mostly_true': {
        'label': 'Mostly True',
        'icon': '✓',
        'color': '#34d399',
        'score': 85,
        'description': 'The claim is largely accurate with minor imprecision'
    },
    'nearly_true': {
        'label': 'Nearly True',
        'icon': '⚡',
        'color': '#60a5fa',
        'score': 75,
        'description': 'The claim is mostly accurate but lacks some context'
    },
    'mixed': {
        'label': 'Mixed',
        'icon': '⚠️',
        'color': '#f59e0b',
        'score': 50,
        'description': 'The claim has both accurate and inaccurate elements'
    },
    'mostly_false': {
        'label': 'Mostly False',
        'icon': '❌',
        'color': '#f97316',
        'score': 25,
        'description': 'The claim is largely inaccurate with some truth'
    },
    'false': {
        'label': 'False',
        'icon': '🚫',
        'color': '#ef4444',
        'score': 0,
        'description': 'The claim is inaccurate and unsupported by evidence'
    },
    'misleading': {
        'label': 'Misleading',
        'icon': '🌀',
        'color': '#8b5cf6',
        'score': 20,
        'description': 'The claim misrepresents facts or lacks proper context'
    },
    'exaggeration': {
        'label': 'Exaggeration',
        'icon': '📈',
        'color': '#06b6d4',
        'score': 40,
        'description': 'The claim overstates or inflates the actual facts'
    },
    'empty_rhetoric': {
        'label': 'Empty Rhetoric',
        'icon': '💨',
        'color': '#94a3b8',
        'score': None,
        'description': 'Vague promises or boasts with no substantive content'
    },
    'unsubstantiated_prediction': {
        'label': 'Unsubstantiated Prediction',
        'icon': '🔮',
        'color': '#a78bfa',
        'score': None,
        'description': 'Future claim with no evidence or plan provided'
    },
    'pattern_of_false_promises': {
        'label': 'Pattern of False Promises',
        'icon': '🔄',
        'color': '#f97316',
        'score': 10,
        'description': 'Speaker has history of similar unfulfilled claims'
    },
    'needs_context': {
        'label': 'Needs Context',
        'icon': '❓',
        'color': '#8b5cf6',
        'score': None,
        'description': 'Cannot verify without additional information'
    },
    'opinion': {
        'label': 'Opinion with Analysis',
        'icon': '💭',
        'color': '#6366f1',
        'score': None,
        'description': 'Subjective claim analyzed for factual elements'
    }
}

# Job management functions
def create_job(transcript: str, source_type: str = 'unknown') -> str:
    """Create a new analysis job"""
    job_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(threading.get_ident())
    
    with job_lock:
        jobs[job_id] = {
            'id': job_id,
            'status': 'created',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'transcript_length': len(transcript),
            'source_type': source_type
        }
    
    return job_id

def update_job(job_id: str, updates: Dict):
    """Update job status"""
    with job_lock:
        if job_id in jobs:
            jobs[job_id].update(updates)
            jobs[job_id]['updated_at'] = datetime.now().isoformat()

def get_job(job_id: str) -> Optional[Dict]:
    """Get job by ID"""
    with job_lock:
        return jobs.get(job_id)

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start transcript analysis - handles all input types"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        transcript = data.get('transcript', '').strip()
        source_type = data.get('source_type', 'text')
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        # Check length
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({'error': f'Transcript too long. Maximum {Config.MAX_TRANSCRIPT_LENGTH} characters.'}), 400
        
        # Minimum length check
        if len(transcript) < 10:
            return jsonify({'error': 'Transcript too short. Please provide more content to analyze.'}), 400
        
        # Create job
        job_id = create_job(transcript, source_type)
        
        # Add metadata
        update_job(job_id, {
            'source_type': source_type,
            'transcript_preview': transcript[:200] + '...' if len(transcript) > 200 else transcript
        })
        
        # Start processing in background
        thread = threading.Thread(target=process_transcript, args=(job_id, transcript))
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Analysis started',
            'source_type': source_type
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/youtube/process', methods=['POST'])
def process_youtube():
    """Process YouTube URL - NEW ENDPOINT"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'No YouTube URL provided'}), 400
        
        # Process YouTube URL
        logger.info(f"Processing YouTube URL: {url}")
        result = youtube_service.process_youtube_url(url)
        
        if not result['success']:
            return jsonify({
                'error': result.get('error', 'Failed to process YouTube video'),
                'suggestion': result.get('suggestion', ''),
                'alternative': result.get('alternative', ''),
                'attempts': result.get('attempts', {})
            }), 400
        
        # Extract transcript
        transcript = result.get('transcript', '')
        if not transcript:
            return jsonify({'error': 'No transcript extracted from video'}), 400
        
        # Create analysis job
        job_id = create_job(transcript, 'youtube')
        
        # Add YouTube-specific metadata
        update_job(job_id, {
            'youtube_metadata': {
                'title': result.get('title', 'Unknown'),
                'duration': result.get('duration', 0),
                'source_type': result.get('source_type', 'youtube'),
                'caption_type': result.get('caption_type', 'unknown'),
                'warning': result.get('warning', '')
            }
        })
        
        # Start processing
        thread = threading.Thread(target=process_transcript, args=(job_id, transcript))
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'YouTube video processed successfully',
            'source_type': result.get('source_type', 'youtube'),
            'caption_type': result.get('caption_type', 'unknown'),
            'title': result.get('title', 'Unknown'),
            'warning': result.get('warning', '')
        })
        
    except Exception as e:
        logger.error(f"YouTube processing error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/youtube/capabilities')
def youtube_capabilities():
    """Get YouTube service capabilities - NEW ENDPOINT"""
    capabilities = youtube_service.get_capabilities()
    return jsonify(capabilities)

@app.route('/api/status/<job_id>')
def get_status(job_id: str):
    """Get job status"""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'status': job.get('status'),
        'progress': job.get('progress', 0),
        'message': job.get('message', ''),
        'error': job.get('error'),
        'source_type': job.get('source_type', 'unknown'),
        'transcript_length': job.get('transcript_length', 0),
        'youtube_metadata': job.get('youtube_metadata', {})
    })

@app.route('/api/results/<job_id>')
def get_results(job_id: str):
    """Get analysis results"""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.get('status') != 'completed':
        return jsonify({'error': 'Analysis not complete'}), 400
    
    return jsonify(job.get('results', {}))

@app.route('/api/export/<job_id>/<format>')
def export_results(job_id: str, format: str):
    """Export results in various formats"""
    if format not in ['json', 'txt', 'pdf']:
        return jsonify({'error': 'Invalid format'}), 400
    
    job = get_job(job_id)
    if not job or job.get('status') != 'completed':
        return jsonify({'error': 'Results not available'}), 404
    
    results = job.get('results', {})
    
    try:
        if format == 'json':
            return jsonify(results)
        
        elif format == 'txt':
            report = generate_text_report(results)
            return report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact_check_{job_id}.txt'
            }
        
        elif format == 'pdf':
            pdf_path = export_service.export_pdf(results, job_id)
            return send_file(pdf_path, as_attachment=True, download_name=f'fact_check_{job_id}.pdf')
            
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcription/validate', methods=['POST'])
def validate_transcription():
    """Validate transcription quality"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        validation_results = {
            'is_valid': True,
            'word_count': len(transcript.split()),
            'character_count': len(transcript),
            'estimated_claims': 0,
            'suggestions': [],
            'quality_score': 0
        }
        
        # Check minimum length
        if len(transcript) < 50:
            validation_results['is_valid'] = False
            validation_results['suggestions'].append('Transcript is too short for meaningful analysis')
        
        # Check for potential claims
        claim_indicators = ['said', 'stated', 'reported', 'according to', 'data shows', 
                          'statistics', '%', 'billion', 'million']
        claim_count = sum(1 for indicator in claim_indicators if indicator.lower() in transcript.lower())
        validation_results['estimated_claims'] = claim_count
        
        if claim_count == 0:
            validation_results['suggestions'].append('Consider recording content with more factual claims')
        
        # Quality score
        quality_score = min(100, (len(transcript) / 100) + (claim_count * 10))
        validation_results['quality_score'] = int(quality_score)
        
        if quality_score < 30:
            validation_results['suggestions'].append('Recording quality appears low. Try clearer audio')
        
        return jsonify(validation_results)
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'features': {
            'text_analysis': True,
            'file_upload': True,
            'youtube_captions': True,
            'youtube_audio_transcription': 'Limited to 30 minutes',
            'live_transcription_microphone': True,
            'live_youtube_streaming': False,  # BE HONEST!
            'export': True
        },
        'limitations': {
            'youtube_live_streams': 'Not supported - process after stream ends',
            'audio_transcription': 'Maximum 30 minutes',
            'real_time_streaming': 'Only from microphone, not from YouTube'
        }
    })

# Processing functions
def process_transcript(job_id: str, transcript: str):
    """Process transcript in background"""
    try:
        # Update progress
        update_job(job_id, {
            'status': 'processing',
            'progress': 10,
            'message': 'Extracting claims...'
        })
        
        # Extract claims
        extraction_result = claim_extractor.extract(transcript)
        claims = extraction_result.get('claims', [])
        speakers = extraction_result.get('speakers', [])
        topics = extraction_result.get('topics', [])
        
        logger.info(f"Claims found: {len(claims)}")
        
        if not claims:
            update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'No verifiable claims found',
                'results': {
                    'claims': [],
                    'fact_checks': [],
                    'summary': 'No verifiable claims were found in the transcript.',
                    'credibility_score': {'score': 0, 'label': 'No claims to verify'},
                    'speakers': speakers,
                    'topics': topics,
                    'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
                    'total_claims': 0,
                    'extraction_method': extraction_result.get('extraction_method', 'unknown')
                }
            })
            return
        
        # Progress update
        update_job(job_id, {
            'progress': 30,
            'message': f'Fact-checking {len(claims)} claims...'
        })
        
        # Fact-check claims
        fact_checks = []
        total_claims = len(claims)
        
        for i, claim in enumerate(claims):
            try:
                # Update progress
                progress = 30 + (i / total_claims * 60)
                update_job(job_id, {
                    'progress': int(progress),
                    'message': f'Checking claim {i+1} of {total_claims}...'
                })
                
                # Fact-check with context
                context = {
                    'transcript': transcript,
                    'speaker': claim.get('speaker', 'Unknown'),
                    'topics': topics
                }
                
                result = fact_checker.check_claim_with_verdict(claim.get('text', ''), context)
                
                if result:
                    fact_checks.append(result)
                    logger.info(f"Fact check {i+1}/{total_claims}: {result.get('verdict', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error checking claim {i+1}: {e}")
                fact_checks.append({
                    'claim': claim.get('text', ''),
                    'speaker': claim.get('speaker', 'Unknown'),
                    'verdict': 'error',
                    'explanation': f'Analysis failed: {str(e)}',
                    'confidence': 0
                })
        
        # Final progress update
        update_job(job_id, {
            'progress': 95,
            'message': 'Generating summary...'
        })
        
        # Calculate credibility score
        credibility_score = calculate_credibility_score(fact_checks)
        
        # Generate summary
        summary = generate_summary(fact_checks, credibility_score, speakers, topics)
        
        # Store results
        results = {
            'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
            'claims': fact_checks,
            'fact_checks': fact_checks,
            'speakers': speakers,
            'topics': topics,
            'credibility_score': credibility_score,
            'summary': summary,
            'total_claims': len(claims),
            'extraction_method': extraction_result.get('extraction_method', 'unknown'),
            'processing_time': datetime.now().isoformat()
        }
        
        update_job(job_id, {
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis complete',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        logger.error(traceback.format_exc())
        update_job(job_id, {
            'status': 'failed',
            'error': str(e),
            'message': 'Analysis failed'
        })

def calculate_credibility_score(fact_checks: List[Dict]) -> Dict:
    """Calculate overall credibility score"""
    if not fact_checks:
        return {'score': 0, 'label': 'No claims', 'breakdown': {}}
    
    verdict_mapping = {
        'true': {'ui_verdict': 'verified_true', 'score': 100},
        'mostly_true': {'ui_verdict': 'verified_true', 'score': 85},
        'nearly_true': {'ui_verdict': 'partially_accurate', 'score': 75},
        'false': {'ui_verdict': 'verified_false', 'score': 0},
        'mostly_false': {'ui_verdict': 'verified_false', 'score': 15},
        'misleading': {'ui_verdict': 'verified_false', 'score': 20},
        'pattern_of_false_promises': {'ui_verdict': 'verified_false', 'score': 10},
        'mixed': {'ui_verdict': 'partially_accurate', 'score': 50},
        'exaggeration': {'ui_verdict': 'partially_accurate', 'score': 40},
        'needs_context': {'ui_verdict': 'unverifiable', 'score': None},
        'opinion': {'ui_verdict': 'unverifiable', 'score': None},
        'empty_rhetoric': {'ui_verdict': 'unverifiable', 'score': None},
        'unsubstantiated_prediction': {'ui_verdict': 'unverifiable', 'score': None},
    }
    
    breakdown = {
        'verified_true': 0,
        'verified_false': 0,
        'partially_accurate': 0,
        'unverifiable': 0
    }
    
    total_score = 0
    scored_claims = 0
    
    for check in fact_checks:
        verdict = check.get('verdict', 'unverifiable')
        mapping = verdict_mapping.get(verdict, {'ui_verdict': 'unverifiable', 'score': None})
        
        ui_verdict = mapping['ui_verdict']
        breakdown[ui_verdict] += 1
        
        score = mapping['score']
        if score is not None:
            total_score += score
            scored_claims += 1
    
    # Calculate overall score
    if scored_claims > 0:
        overall_score = int(total_score / scored_claims)
    else:
        overall_score = 0
    
    # Determine label
    if overall_score >= 80:
        label = 'Highly Credible'
    elif overall_score >= 60:
        label = 'Mostly Credible'
    elif overall_score >= 40:
        label = 'Mixed Credibility'
    elif overall_score >= 20:
        label = 'Low Credibility'
    elif scored_claims > 0:
        label = 'Poor Credibility'
    else:
        label = 'Unverifiable'
    
    return {
        'score': overall_score,
        'label': label,
        'breakdown': breakdown,
        'scored_claims': scored_claims,
        'total_claims': len(fact_checks)
    }

def generate_summary(fact_checks: List[Dict], credibility_score: Dict, speakers: List[str], topics: List[str]) -> str:
    """Generate analysis summary"""
    total_claims = len(fact_checks)
    if total_claims == 0:
        return "No verifiable claims were found in the transcript for fact-checking."
    
    score = credibility_score.get('score', 0)
    breakdown = credibility_score.get('breakdown', {})
    
    summary_parts = []
    
    summary_parts.append(f"Analysis of {total_claims} factual claims revealed a credibility score of {score}/100.")
    
    if breakdown.get('verified_true', 0) > 0:
        summary_parts.append(f"{breakdown['verified_true']} claims were verified as true or mostly accurate.")
    
    if breakdown.get('verified_false', 0) > 0:
        summary_parts.append(f"{breakdown['verified_false']} claims were found to be false or misleading.")
    
    if breakdown.get('partially_accurate', 0) > 0:
        summary_parts.append(f"{breakdown['partially_accurate']} claims were partially accurate or mixed.")
    
    if breakdown.get('unverifiable', 0) > 0:
        summary_parts.append(f"{breakdown['unverifiable']} claims could not be verified with available sources.")
    
    if len(speakers) > 1:
        summary_parts.append(f"Multiple speakers identified: {', '.join(speakers[:3])}{'...' if len(speakers) > 3 else ''}.")
    
    return " ".join(summary_parts)

def generate_text_report(results: Dict) -> str:
    """Generate text report for export"""
    report = []
    report.append("FACT-CHECKING REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    report.append("SUMMARY")
    report.append("-" * 20)
    report.append(results.get('summary', 'No summary available'))
    report.append("")
    
    credibility = results.get('credibility_score', {})
    report.append(f"CREDIBILITY SCORE: {credibility.get('score', 0)}/100 ({credibility.get('label', 'Unknown')})")
    report.append("")
    
    fact_checks = results.get('fact_checks', [])
    report.append(f"DETAILED FACT CHECKS ({len(fact_checks)} claims)")
    report.append("-" * 40)
    
    for i, fc in enumerate(fact_checks, 1):
        report.append(f"\n{i}. CLAIM: {fc.get('claim', 'Unknown')}")
        report.append(f"   Speaker: {fc.get('speaker', 'Unknown')}")
        report.append(f"   Verdict: {fc.get('verdict', 'Unknown').upper().replace('_', ' ')}")
        
        if fc.get('confidence'):
            report.append(f"   Confidence: {fc.get('confidence')}%")
            
        report.append(f"   Analysis: {fc.get('explanation', 'No explanation available')}")
        
        if fc.get('sources'):
            report.append(f"   Sources: {', '.join(fc['sources'])}")
    
    return "\n".join(report)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Main
if __name__ == '__main__':
    required_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Fact checking will have limited functionality")
    
    logger.info("=== TRANSCRIPT FACT CHECKER STARTING ===")
    logger.info("Features available:")
    logger.info("✓ Text transcript analysis")
    logger.info("✓ File upload support (TXT, SRT, VTT)")
    logger.info("✓ YouTube videos with captions")
    logger.info("✓ YouTube audio transcription (max 30 min)")
    logger.info("✓ Microphone live transcription")
    logger.info("✗ YouTube live streaming - NOT SUPPORTED")
    logger.info("✓ Export functionality (JSON, TXT, PDF)")
    
    # Be honest about YouTube capabilities
    youtube_caps = youtube_service.get_capabilities()
    logger.info("\nYouTube Capabilities:")
    for key, value in youtube_caps['supported'].items():
        if value is True:
            logger.info(f"  ✓ {key}")
        elif value is False:
            logger.info(f"  ✗ {key}")
        else:
            logger.info(f"  ⚠ {key}: {value}")
    
    if Config.OPENAI_API_KEY:
        logger.info("✓ AI-powered claim extraction enabled")
    else:
        logger.warning("⚠ AI claim extraction disabled (no OpenAI key)")
        
    if Config.GOOGLE_FACTCHECK_API_KEY:
        logger.info("✓ Google Fact Check API enabled")
    else:
        logger.warning("⚠ Google Fact Check API disabled")
    
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting server on port {port}...")
    logger.info("==========================================")
    
    app.run(host='0.0.0.0', port=port, debug=False)
