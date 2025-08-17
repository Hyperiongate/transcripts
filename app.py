"""
Enhanced Flask Application with AI Filtering and Improved Accuracy
Main application file with all improvements integrated
"""
import os
import uuid
import logging
import traceback
from datetime import datetime
from threading import Thread
from collections import defaultdict

from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS

# Import configuration
from config import Config

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimsExtractor
from services.factcheck import FactChecker
from services.job_storage import JobStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']
CORS(app)

# Initialize services
transcript_processor = TranscriptProcessor()
claims_extractor = ClaimsExtractor(openai_api_key=Config.OPENAI_API_KEY)
fact_checker = FactChecker(Config)
job_storage = JobStorage()

# Simple speaker context database
SPEAKER_CONTEXT = {
    'donald trump': {
        'full_name': 'Donald J. Trump',
        'role': '45th and 47th President of the United States',
        'party': 'Republican',
        'criminal_record': 'First U.S. President to be criminally convicted (34 felony counts of falsifying business records in New York, May 2024)',
        'legal_issues': [
            'Convicted on 34 felony counts in New York (May 2024)',
            'Indicted in Georgia on racketeering charges (August 2023)',
            'Indicted federally for classified documents mishandling (June 2023)',
            'Indicted federally for January 6th events (August 2023)'
        ],
        'fraud_history': 'Trump University settled for $25 million (2016), Trump Foundation dissolved after fraud findings (2018)',
        'fact_check_history': 'Made 30,573 false or misleading claims during presidency per Washington Post database',
        'credibility_notes': 'Known for hyperbolic statements and disputed claims'
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

# Routes
@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Enhanced analyze endpoint with all improvements"""
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
            'id': job_id,
            'status': 'processing',
            'progress': 0,
            'source': source,
            'created_at': datetime.now().isoformat()
        }
        job_storage.set(job_id, job_data)
        
        # Start processing in background
        thread = Thread(target=process_transcript_enhanced, args=(job_id, transcript, source))
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

def process_transcript_enhanced(job_id: str, transcript: str, source: str):
    """Enhanced transcript processing with all improvements"""
    try:
        # Update progress
        job_storage.update(job_id, {'status': 'processing', 'progress': 10})
        
        # Step 1: Process transcript
        processed_transcript = transcript_processor.process(transcript)
        job_storage.update(job_id, {'progress': 20})
        
        # Step 2: Extract context (speakers and topics)
        speakers, topics = claims_extractor.extract_context(processed_transcript)
        
        # Identify main speaker
        speaker_name = None
        speaker_info = None
        
        # Check source for speaker
        source_lower = source.lower()
        for known_speaker, info in SPEAKER_CONTEXT.items():
            if known_speaker in source_lower:
                speaker_name = info['full_name']
                speaker_info = info
                break
        
        # If not found in source, check speakers list
        if not speaker_name and speakers:
            for speaker in speakers:
                speaker_lower = speaker.lower()
                for known_speaker, info in SPEAKER_CONTEXT.items():
                    if known_speaker in speaker_lower or speaker_lower in known_speaker:
                        speaker_name = info['full_name']
                        speaker_info = info
                        break
                if speaker_name:
                    break
        
        job_storage.update(job_id, {'progress': 30})
        
        # Step 3: Extract claims with AI filtering
        claims_data = claims_extractor.extract_claims(
            processed_transcript,
            max_claims=Config.MAX_CLAIMS_TO_CHECK
        )
        
        # Get prioritized claim texts
        claims = claims_extractor.prioritize_claims(claims_data)
        
        logger.info(f"Extracted {len(claims)} factual claims after AI filtering")
        job_storage.update(job_id, {'progress': 50, 'total_claims': len(claims)})
        
        # Step 4: Fact-check claims
        fact_check_results = fact_checker.check_claims_batch(claims, source)
        
        # Update progress during fact-checking
        for i, result in enumerate(fact_check_results):
            progress = 50 + int((i + 1) / len(fact_check_results) * 40)
            job_storage.update(job_id, {'progress': progress})
        
        # Step 5: Calculate credibility score
        credibility_score = calculate_enhanced_credibility_score(fact_check_results)
        
        # Step 6: Generate summary
        summary = generate_enhanced_summary(
            fact_check_results,
            credibility_score,
            speaker_name,
            speaker_info
        )
        
        # Prepare final results
        results = {
            'success': True,
            'source': source,
            'timestamp': datetime.now().isoformat(),
            'speaker': speaker_name,
            'speaker_context': get_speaker_context_summary(speaker_info) if speaker_info else None,
            'total_claims': len(claims),
            'checked_claims': len(fact_check_results),
            'fact_checks': fact_check_results,
            'credibility_score': credibility_score,
            'credibility_label': get_credibility_label(credibility_score),
            'conversational_summary': summary,
            'context_summary': {
                'speakers': speakers,
                'topics': topics
            },
            'analysis_mode': 'AI-enhanced' if Config.OPENAI_API_KEY else 'Pattern-based'
        }
        
        # Store results
        job_storage.update(job_id, {
            'status': 'completed',
            'progress': 100,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        job_storage.update(job_id, {
            'status': 'failed',
            'error': str(e),
            'progress': 0
        })

def get_speaker_context_summary(speaker_info: dict) -> dict:
    """Format speaker context for display"""
    if not speaker_info:
        return None
    
    context = {
        'speaker': speaker_info.get('full_name'),
        'role': speaker_info.get('role'),
        'party': speaker_info.get('party'),
        'has_context': True
    }
    
    # Add concerning information if present
    if speaker_info.get('criminal_record'):
        context['criminal_record'] = speaker_info['criminal_record']
    
    if speaker_info.get('fraud_history'):
        context['fraud_history'] = speaker_info['fraud_history']
    
    if speaker_info.get('legal_issues'):
        context['legal_issues'] = speaker_info['legal_issues']
    
    if speaker_info.get('fact_check_history'):
        context['fact_check_history'] = speaker_info['fact_check_history']
    
    if speaker_info.get('credibility_notes'):
        context['credibility_notes'] = speaker_info['credibility_notes']
    
    return context

def calculate_enhanced_credibility_score(fact_checks: list) -> int:
    """Calculate credibility score with improved weighting"""
    if not fact_checks:
        return 100
    
    total_weight = 0
    weighted_score = 0
    
    # Enhanced verdict weights with new verdicts
    verdict_scores = {
        'true': 100,
        'mostly_true': 85,
        'mixed': 50,
        'unclear': 45,  # NEW: Ambiguous claims
        'misleading': 25,  # NEW: Technically true but deceptive
        'lacks_context': 40,
        'unsubstantiated': 30,
        'mostly_false': 15,
        'false': 0,
        'deceptive': -20,  # Penalty for deliberate deception
        'unverified': 50,  # Neutral when we can't verify
        'opinion': None  # Skip opinions
    }
    
    for check in fact_checks:
        verdict = check.get('verdict', 'unverified').lower().replace(' ', '_')
        
        # Skip opinions
        if verdict == 'opinion':
            continue
        
        # Get confidence weight
        confidence = check.get('confidence', 50) / 100
        
        # Additional weight factors
        weight = confidence
        
        # Higher weight for claims with official sources
        if check.get('source') and '.gov' in check.get('source', '').lower():
            weight *= 1.5
        
        # Higher weight for API responses
        if check.get('api_response'):
            weight *= 1.2
        
        # Lower weight for pattern-only analysis
        if check.get('source') == 'Pattern Analysis':
            weight *= 0.8
        
        score = verdict_scores.get(verdict, 50)
        if score is not None:
            weighted_score += score * weight
            total_weight += weight
    
    if total_weight == 0:
        return 50
    
    final_score = int(weighted_score / total_weight)
    
    # Ensure score is within bounds
    return max(0, min(100, final_score))

def generate_enhanced_summary(fact_checks: list, credibility_score: int, 
                            speaker: str, speaker_info: dict) -> str:
    """Generate enhanced conversational summary with all context"""
    if not fact_checks:
        return "No claims were found to fact-check in this transcript."
    
    summary_parts = []
    
    # Add speaker context if concerning
    if speaker_info:
        if speaker_info.get('criminal_record'):
            summary_parts.append(
                f"⚠️ IMPORTANT CONTEXT: {speaker} is a {speaker_info['criminal_record']}. "
                f"This background is relevant when evaluating the credibility of their statements."
            )
        
        if speaker_info.get('fraud_history'):
            summary_parts.append(f"Financial misconduct history: {speaker_info['fraud_history']}")
    
    # Analyze current performance
    verdict_counts = defaultdict(int)
    for check in fact_checks:
        verdict = check.get('verdict', 'unverified').lower().replace(' ', '_')
        verdict_counts[verdict] += 1
    
    # Overall assessment
    total_claims = len(fact_checks)
    
    if credibility_score >= 80:
        assessment = f"This transcript demonstrates high credibility ({credibility_score}%). "
    elif credibility_score >= 60:
        assessment = f"This transcript shows moderate credibility ({credibility_score}%). "
    elif credibility_score >= 40:
        assessment = f"This transcript has credibility concerns ({credibility_score}%). "
    else:
        assessment = f"This transcript has serious credibility issues ({credibility_score}%). "
    
    summary_parts.append(assessment)
    
    # Specific findings
    findings = []
    
    if verdict_counts['true'] + verdict_counts['mostly_true'] > 0:
        findings.append(f"{verdict_counts['true'] + verdict_counts['mostly_true']} verified as accurate")
    
    if verdict_counts['false'] + verdict_counts['mostly_false'] > 0:
        findings.append(f"{verdict_counts['false'] + verdict_counts['mostly_false']} proven false")
    
    if verdict_counts['misleading'] > 0:
        findings.append(f"⚠️ {verdict_counts['misleading']} misleading (technically true but deceptive)")
    
    if verdict_counts['unclear'] > 0:
        findings.append(f"{verdict_counts['unclear']} too unclear to verify")
    
    if verdict_counts['lacks_context'] > 0:
        findings.append(f"{verdict_counts['lacks_context']} missing critical context")
    
    if findings:
        summary_parts.append(f"Out of {total_claims} claims analyzed: " + ", ".join(findings) + ".")
    
    # Pattern detection
    if verdict_counts['deceptive'] >= 3:
        summary_parts.append(
            "🚨 PATTERN ALERT: Multiple deliberately deceptive statements detected. "
            "This suggests intentional misrepresentation rather than honest mistakes."
        )
    elif verdict_counts['false'] + verdict_counts['mostly_false'] >= 5:
        summary_parts.append(
            "⚠️ PATTERN: High number of false claims indicates unreliable information. "
            "Verify independently before accepting any claims from this source."
        )
    elif verdict_counts['lacks_context'] >= 4:
        summary_parts.append(
            "📊 PATTERN: Frequent omission of context suggests selective presentation of facts."
        )
    
    return " ".join(summary_parts)

def get_credibility_label(score: int) -> str:
    """Get label for credibility score"""
    if score >= 80:
        return "High Credibility"
    elif score >= 60:
        return "Moderate Credibility"
    elif score >= 40:
        return "Low Credibility"
    else:
        return "Very Low Credibility"

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    return jsonify({
        'success': True,
        'status': job_data.get('status'),
        'progress': job_data.get('progress', 0),
        'total_claims': job_data.get('total_claims', 0),
        'error': job_data.get('error')
    })

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    job_data = job_storage.get(job_id)
    
    if not job_data:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    if job_data.get('status') != 'completed':
        return jsonify({'success': False, 'error': 'Analysis not complete'}), 400
    
    return jsonify(job_data.get('results', {}))

@app.route('/api/export/<job_id>/<format_type>')
def export_results(job_id, format_type):
    """Export results in various formats"""
    try:
        job_data = job_storage.get(job_id)
        
        if not job_data or job_data.get('status') != 'completed':
            return jsonify({'success': False, 'error': 'Results not available'}), 404
        
        results = job_data.get('results', {})
        
        if format_type == 'pdf':
            # PDF generation would require additional library
            return jsonify({'success': False, 'error': 'PDF export not yet implemented'}), 501
                
        elif format_type == 'json':
            return jsonify(results)
            
        elif format_type == 'txt':
            report = generate_text_report(results)
            return report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact-check-{job_id}.txt'
            }
            
        else:
            return jsonify({'success': False, 'error': 'Invalid format'}), 400
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_text_report(results: dict) -> str:
    """Generate enhanced text report"""
    lines = []
    lines.append("ENHANCED TRANSCRIPT FACT CHECK REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    lines.append(f"Source: {results.get('source', 'Unknown')}")
    lines.append(f"Analysis Mode: {results.get('analysis_mode', 'Standard')}")
    
    # Speaker information
    if results.get('speaker'):
        lines.append(f"\nSPEAKER: {results['speaker']}")
        
        if results.get('speaker_context'):
            ctx = results['speaker_context']
            if ctx.get('role'):
                lines.append(f"Role: {ctx['role']}")
            if ctx.get('criminal_record'):
                lines.append(f"⚠️ Criminal Record: {ctx['criminal_record']}")
            if ctx.get('fraud_history'):
                lines.append(f"⚠️ Fraud History: {ctx['fraud_history']}")
    
    # Credibility summary
    lines.append(f"\nCREDIBILITY SCORE: {results.get('credibility_score', 0)}% - {results.get('credibility_label', 'Unknown')}")
    
    # Summary
    if results.get('conversational_summary'):
        lines.append("\nSUMMARY:")
        lines.append("-" * 70)
        lines.append(results['conversational_summary'])
    
    # Context summary
    if results.get('context_summary'):
        ctx = results['context_summary']
        if ctx.get('topics'):
            lines.append(f"\nTOPICS IDENTIFIED: {', '.join(ctx['topics'])}")
    
    # Detailed fact checks
    lines.append("\nDETAILED FACT CHECKS:")
    lines.append("-" * 70)
    
    for i, check in enumerate(results.get('fact_checks', []), 1):
        lines.append(f"\n{i}. CLAIM: {check.get('claim', 'N/A')}")
        
        if check.get('temporal_note'):
            lines.append(f"   Temporal Context: {check['temporal_note']}")
        
        lines.append(f"   VERDICT: {check.get('verdict', 'Unknown').upper()}")
        lines.append(f"   CONFIDENCE: {check.get('confidence', 0)}%")
        lines.append(f"   EXPLANATION: {check.get('explanation', 'No explanation available')}")
        
        if check.get('actual_value') and check.get('claimed_value'):
            lines.append(f"   NUMBERS: Claimed {check['claimed_value']} vs Actual {check['actual_value']}")
        
        if check.get('missing_context'):
            lines.append(f"   MISSING CONTEXT: {check['missing_context']}")
        
        if check.get('source'):
            lines.append(f"   SOURCE: {check['source']}")
    
    # Statistics
    lines.append("\nSTATISTICS:")
    lines.append("-" * 70)
    lines.append(f"Total Claims Analyzed: {results.get('checked_claims', 0)}")
    
    # Count verdicts
    verdict_counts = defaultdict(int)
    for check in results.get('fact_checks', []):
        verdict = check.get('verdict', 'unverified')
        verdict_counts[verdict] += 1
    
    for verdict, count in sorted(verdict_counts.items()):
        lines.append(f"{verdict.replace('_', ' ').title()}: {count}")
    
    return "\n".join(lines)

if __name__ == '__main__':
    # Validate configuration
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    # Run app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
