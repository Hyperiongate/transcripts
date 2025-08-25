#!/usr/bin/env python3
"""
Main Flask application for Political Transcript Fact Checker
Enhanced with proper verdict mapping and insightful summaries
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
from services.comprehensive_factcheck import FactChecker
from services.export import ExportService

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

# In-memory job storage (replace with Redis in production)
jobs = {}
job_lock = threading.Lock()

# Enhanced verdict categories with visual elements
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
        'icon': '🔵',
        'color': '#6ee7b7',
        'score': 70,
        'description': 'Largely accurate but missing some context'
    },
    'exaggeration': {
        'label': 'Exaggeration',
        'icon': '📏',
        'color': '#fbbf24',
        'score': 50,
        'description': 'Based on truth but overstated'
    },
    'misleading': {
        'label': 'Misleading',
        'icon': '⚠️',
        'color': '#f59e0b',
        'score': 35,
        'description': 'Contains truth but creates false impression'
    },
    'mostly_false': {
        'label': 'Mostly False',
        'icon': '❌',
        'color': '#f87171',
        'score': 20,
        'description': 'Significant inaccuracies with grain of truth'
    },
    'false': {
        'label': 'False',
        'icon': '❌',
        'color': '#ef4444',
        'score': 0,
        'description': 'Demonstrably incorrect'
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
def create_job(transcript: str) -> str:
    """Create a new analysis job"""
    job_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(threading.get_ident())
    
    with job_lock:
        jobs[job_id] = {
            'id': job_id,
            'status': 'created',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'transcript_length': len(transcript)
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
    """Start transcript analysis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        transcript = data.get('transcript', '').strip()
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        # Check length
        if len(transcript) > Config.MAX_TRANSCRIPT_LENGTH:
            return jsonify({'error': f'Transcript too long. Maximum {Config.MAX_TRANSCRIPT_LENGTH} characters.'}), 400
        
        # Create job
        job_id = create_job(transcript)
        
        # Start processing in background
        thread = threading.Thread(target=process_transcript, args=(job_id, transcript))
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Analysis started'
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

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
        'error': job.get('error')
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
            # Generate text report
            report = generate_text_report(results)
            return report, 200, {
                'Content-Type': 'text/plain',
                'Content-Disposition': f'attachment; filename=fact_check_{job_id}.txt'
            }
        
        elif format == 'pdf':
            # Generate PDF
            pdf_path = export_service.export_pdf(results, job_id)
            return send_file(pdf_path, as_attachment=True, download_name=f'fact_check_{job_id}.pdf')
            
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
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
        logger.info(f"Extraction result keys: {extraction_result.keys() if extraction_result else 'None'}")
        
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
                    'credibility_score': None
                }
            })
            return
        
        # Update progress
        update_job(job_id, {
            'progress': 30,
            'message': f'Fact-checking {len(claims)} claims...'
        })
        
        # Fact check each claim
        fact_checks = []
        for i, claim in enumerate(claims):
            try:
                # Update progress
                progress = 30 + int((i / len(claims)) * 60)
                update_job(job_id, {
                    'progress': progress,
                    'message': f'Checking claim {i+1} of {len(claims)}...'
                })
                
                # Check claim
                result = fact_checker.check_claim_with_verdict(
                    claim.get('text', ''),
                    context={
                        'speaker': claim.get('speaker'),
                        'transcript': transcript
                    }
                )
                
                # Skip None results (trivial claims)
                if result is not None:
                    # Make sure we have the claim text in the result
                    result['claim'] = claim.get('text', '')
                    result['speaker'] = claim.get('speaker', 'Unknown')
                    fact_checks.append(result)
                
            except Exception as e:
                logger.error(f"Error checking claim {i}: {e}")
                fact_checks.append({
                    'claim': claim.get('text', ''),
                    'speaker': claim.get('speaker', 'Unknown'),
                    'verdict': 'needs_context',
                    'explanation': f'Error during verification: {str(e)}',
                    'confidence': 0,
                    'sources': []
                })
        
        # Calculate credibility score with proper mapping
        credibility_score = calculate_credibility_score(fact_checks)
        
        # Generate insightful summary
        summary = generate_summary(fact_checks, credibility_score, speakers, topics)
        
        logger.info(f"Fact checking completed: {len(fact_checks)} claims checked")
        
        # Store results
        results = {
            'transcript_preview': transcript[:500] + '...' if len(transcript) > 500 else transcript,
            'claims': fact_checks,  # For backward compatibility
            'fact_checks': fact_checks,
            'speakers': speakers,
            'topics': topics,
            'credibility_score': credibility_score,
            'summary': summary,
            'total_claims': len(claims),
            'extraction_method': extraction_result.get('extraction_method', 'unknown')
        }
        
        logger.info(f"Results prepared with {len(results.get('fact_checks', []))} fact checks")
        
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
    """Calculate overall credibility score with proper verdict mapping"""
    if not fact_checks:
        return {'score': 0, 'label': 'No claims', 'breakdown': {}}
    
    # Map internal verdicts to UI verdicts
    verdict_mapping = {
        # True verdicts
        'true': 'verified_true',
        'mostly_true': 'verified_true',
        'nearly_true': 'partially_accurate',
        
        # False verdicts
        'false': 'verified_false',
        'mostly_false': 'verified_false',
        'misleading': 'verified_false',
        'pattern_of_false_promises': 'verified_false',
        
        # Mixed/uncertain
        'mixed': 'partially_accurate',
        'exaggeration': 'partially_accurate',
        
        # Unverifiable
        'needs_context': 'unverifiable',
        'opinion': 'unverifiable',
        'empty_rhetoric': 'empty_rhetoric',  # Keep as separate category
        'unsubstantiated_prediction': 'unsubstantiated_prediction'  # Keep as separate
    }
    
    # Count verdicts with mapping
    verdict_counts = {
        'verified_true': 0,
        'verified_false': 0,
        'partially_accurate': 0,
        'unverifiable': 0,
        'empty_rhetoric': 0,
        'unsubstantiated_prediction': 0
    }
    
    total_score = 0
    scored_claims = 0
    
    # Track worst offenders
    false_claims = []
    empty_rhetoric_claims = []
    
    for fc in fact_checks:
        if fc is None:  # Skip None results from trivial claims
            continue
            
        verdict = fc.get('verdict', 'unverifiable')
        mapped_verdict = verdict_mapping.get(verdict, 'unverifiable')
        
        # Count the mapped verdict
        if mapped_verdict in verdict_counts:
            verdict_counts[mapped_verdict] += 1
        else:
            verdict_counts['unverifiable'] += 1
        
        # Track egregious claims
        if mapped_verdict == 'verified_false':
            false_claims.append(fc)
        elif verdict == 'empty_rhetoric':
            empty_rhetoric_claims.append(fc)
        
        # Calculate score
        verdict_info = VERDICT_CATEGORIES.get(verdict, {})
        if verdict_info.get('score') is not None:
            total_score += verdict_info['score']
            scored_claims += 1
    
    # Calculate average score
    if scored_claims > 0:
        score = int(total_score / scored_claims)
    else:
        score = 50  # Default for unverifiable claims
    
    # Determine label with more nuance
    rhetoric_ratio = len(empty_rhetoric_claims) / len(fact_checks) if fact_checks else 0
    false_ratio = len(false_claims) / len(fact_checks) if fact_checks else 0
    
    if rhetoric_ratio > 0.3:
        label = 'Heavy on Empty Rhetoric'
    elif false_ratio > 0.3:
        label = 'Highly Misleading'
    elif score >= 90:
        label = 'Highly Credible'
    elif score >= 70:
        label = 'Mostly Credible'
    elif score >= 50:
        label = 'Mixed Credibility'
    elif score >= 30:
        label = 'Low Credibility'
    else:
        label = 'Very Low Credibility'
    
    return {
        'score': score,
        'label': label,
        'breakdown': verdict_counts,
        'verdict_counts': verdict_counts,  # For backward compatibility
        'total_claims': len([fc for fc in fact_checks if fc is not None]),
        'scored_claims': scored_claims,
        'worst_claims': sorted(false_claims, key=lambda x: x.get('confidence', 0), reverse=True)[:3],
        'empty_rhetoric_count': len(empty_rhetoric_claims),
        'false_claims': false_claims,
        'rhetoric_claims': empty_rhetoric_claims
    }

def generate_summary(fact_checks: List[Dict], credibility_score: Dict, speakers: List[str], topics: List[str]) -> str:
    """Generate insightful analysis summary with visual flair"""
    total = credibility_score.get('total_claims', 0)
    score = credibility_score.get('score', 0)
    label = credibility_score.get('label', 'Unknown')
    breakdown = credibility_score.get('breakdown', {})
    
    # Start with a visual score indicator
    if score >= 80:
        score_visual = "🟢🟢🟢🟢🟢"
    elif score >= 60:
        score_visual = "🟡🟡🟡🟡⚪"
    elif score >= 40:
        score_visual = "🟠🟠🟠⚪⚪"
    elif score >= 20:
        score_visual = "🔴🔴⚪⚪⚪"
    else:
        score_visual = "🔴⚪⚪⚪⚪"
    
    summary_parts = []
    
    # Headline with visual impact
    summary_parts.append(f"# 📊 FACT CHECK ANALYSIS COMPLETE")
    summary_parts.append(f"## Credibility Score: {score}/100 {score_visual}")
    summary_parts.append(f"### Overall Assessment: **{label.upper()}**")
    summary_parts.append("")
    
    # Executive summary
    if total == 0:
        summary_parts.append("No verifiable claims found in this transcript.")
        return "\n".join(summary_parts)
    
    summary_parts.append(f"Analyzed **{total} claims** from {len(speakers)} speaker(s)")
    summary_parts.append("")
    
    # Key findings with visual hierarchy
    summary_parts.append("## 🔍 KEY FINDINGS:")
    
    if breakdown.get('verified_false', 0) > 0:
        summary_parts.append(f"### 🚨 **ALERT: {breakdown['verified_false']} FALSE CLAIMS DETECTED**")
        
        # Show worst false claims
        worst_claims = credibility_score.get('worst_claims', [])
        if worst_claims:
            summary_parts.append("#### Most Egregious False Claims:")
            for i, claim in enumerate(worst_claims[:3], 1):
                claim_text = claim.get('claim', '')[:80] + '...' if len(claim.get('claim', '')) > 80 else claim.get('claim', '')
                summary_parts.append(f"{i}. **\"{claim_text}\"**")
                summary_parts.append(f"   - Speaker: {claim.get('speaker', 'Unknown')}")
                summary_parts.append(f"   - Reality: {claim.get('explanation', '')[:150]}...")
                summary_parts.append("")
    
    if breakdown.get('empty_rhetoric', 0) > 0:
        summary_parts.append(f"### 💨 **{breakdown['empty_rhetoric']} EMPTY PROMISES** detected")
        summary_parts.append("Claims with no specific plans, policies, or evidence provided.")
        summary_parts.append("")
    
    # Positive findings
    if breakdown.get('verified_true', 0) > 0:
        summary_parts.append(f"### ✅ {breakdown['verified_true']} claims VERIFIED AS TRUE")
    
    if breakdown.get('partially_accurate', 0) > 0:
        summary_parts.append(f"### ⚠️  {breakdown['partially_accurate']} claims PARTIALLY ACCURATE")
    
    if breakdown.get('unverifiable', 0) > 0:
        summary_parts.append(f"### ❓ {breakdown['unverifiable']} claims UNVERIFIABLE")
    
    summary_parts.append("")
    
    # Pattern analysis
    if speakers and len(speakers) > 0:
        summary_parts.append("## 👥 SPEAKER ANALYSIS:")
        
        # Analyze each speaker's claims
        speaker_stats = {}
        for fc in fact_checks:
            if fc is None:
                continue
            speaker = fc.get('speaker', 'Unknown')
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {'total': 0, 'false': 0, 'true': 0, 'rhetoric': 0}
            
            speaker_stats[speaker]['total'] += 1
            verdict = fc.get('verdict', '')
            if verdict in ['false', 'mostly_false', 'misleading']:
                speaker_stats[speaker]['false'] += 1
            elif verdict in ['true', 'mostly_true']:
                speaker_stats[speaker]['true'] += 1
            elif verdict == 'empty_rhetoric':
                speaker_stats[speaker]['rhetoric'] += 1
        
        for speaker, stats in speaker_stats.items():
            if stats['total'] > 0:
                accuracy = (stats['true'] / stats['total']) * 100 if stats['total'] > 0 else 0
                summary_parts.append(f"**{speaker}**: {stats['total']} claims")
                summary_parts.append(f"- Accuracy rate: {accuracy:.0f}%")
                if stats['false'] > 0:
                    summary_parts.append(f"- ❌ False claims: {stats['false']}")
                if stats['rhetoric'] > 0:
                    summary_parts.append(f"- 💨 Empty rhetoric: {stats['rhetoric']}")
                summary_parts.append("")
    
    # Bottom line assessment
    summary_parts.append("## 📊 BOTTOM LINE:")
    
    if score < 30:
        summary_parts.append("### ⛔ **SEVERE CREDIBILITY ISSUES**")
        summary_parts.append("This transcript contains numerous false or misleading claims. Readers should be **highly skeptical** of the information presented.")
    elif score < 50:
        summary_parts.append("### ⚠️  **SIGNIFICANT ACCURACY CONCERNS**")
        summary_parts.append("Multiple false or misleading claims detected. **Verify independently** before accepting these claims.")
    elif score < 70:
        summary_parts.append("### 🟡 **MIXED RELIABILITY**")
        summary_parts.append("Some claims check out, others don't. **Use caution** and cross-reference important claims.")
    elif score < 90:
        summary_parts.append("### ✅ **GENERALLY RELIABLE**")
        summary_parts.append("Most claims are supported by evidence with only minor issues identified.")
    else:
        summary_parts.append("### 💚 **HIGHLY CREDIBLE**")
        summary_parts.append("Claims are well-supported by multiple sources and evidence.")
    
    # Value proposition
    false_count = breakdown.get('verified_false', 0)
    rhetoric_count = breakdown.get('empty_rhetoric', 0)
    
    if false_count > 0 or rhetoric_count > 0:
        summary_parts.append("")
        summary_parts.append("## 💡 VALUE PROVIDED:")
        if false_count > 0:
            summary_parts.append(f"✓ Identified **{false_count} false claims** you might have believed")
        if rhetoric_count > 0:
            summary_parts.append(f"✓ Exposed **{rhetoric_count} empty promises** lacking substance")
        summary_parts.append("✓ Saved you time by analyzing claims against multiple sources")
        summary_parts.append("✓ Provided context and evidence for informed judgment")
    
    # Call to action
    summary_parts.append("")
    summary_parts.append("---")
    summary_parts.append("*💡 Tip: Click on individual claims below for detailed analysis and sources.*")
    
    return "\n".join(summary_parts)

def generate_text_report(results: Dict) -> str:
    """Generate text format report"""
    report = []
    report.append("POLITICAL TRANSCRIPT FACT CHECK REPORT")
    report.append("=" * 70)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Summary
    report.append("EXECUTIVE SUMMARY")
    report.append("-" * 30)
    summary = results.get('summary', 'No summary available')
    # Convert markdown to plain text
    summary = summary.replace('### ', '').replace('## ', '').replace('# ', '')
    summary = summary.replace('**', '').replace('*', '')
    report.append(summary)
    report.append("")
    
    # Credibility Score
    cred = results.get('credibility_score', {})
    report.append("CREDIBILITY ANALYSIS")
    report.append("-" * 30)
    report.append(f"Overall Score: {cred.get('score', 'N/A')}/100")
    report.append(f"Assessment: {cred.get('label', 'Unknown')}")
    report.append("")
    
    breakdown = cred.get('breakdown', {})
    if breakdown:
        report.append("Claims Breakdown:")
        report.append(f"  Verified True: {breakdown.get('verified_true', 0)}")
        report.append(f"  Verified False: {breakdown.get('verified_false', 0)}")
        report.append(f"  Partially Accurate: {breakdown.get('partially_accurate', 0)}")
        report.append(f"  Unverifiable: {breakdown.get('unverifiable', 0)}")
        if breakdown.get('empty_rhetoric', 0) > 0:
            report.append(f"  Empty Rhetoric: {breakdown.get('empty_rhetoric', 0)}")
    report.append("")
    
    # Detailed Claims
    report.append("DETAILED FACT CHECKS")
    report.append("-" * 30)
    
    fact_checks = results.get('fact_checks', [])
    for i, fc in enumerate(fact_checks, 1):
        if fc is None:
            continue
            
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
    # Check for required environment variables
    required_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Fact checking will have limited functionality without these keys")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
