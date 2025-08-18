"""
Transcript Fact Checker - Main Flask Application
"""
import os
import logging
import uuid
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import redis
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io

# Import services
from services.transcript import TranscriptProcessor
from services.claims import ClaimExtractor
from services.factcheck import FactChecker
from services.youtube_audio_transcriber import YouTubeAudioTranscriber
from config import Config

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MongoDB
mongo_client = MongoClient(Config.MONGODB_URI)
db = mongo_client[Config.MONGODB_DB_NAME]
jobs_collection = db['jobs']
results_collection = db['results']

# Initialize Redis
redis_client = redis.from_url(Config.REDIS_URL)

# Initialize services
transcript_processor = TranscriptProcessor()
claim_extractor = ClaimExtractor()
fact_checker = FactChecker()
youtube_transcriber = YouTubeAudioTranscriber()

# Enhanced speaker database with current information
SPEAKER_DATABASE = {
    'donald trump': {
        'full_name': 'Donald J. Trump',
        'role': '45th and 47th President of the United States',
        'party': 'Republican',
        'criminal_record': 'Multiple indictments in 2023-2024',
        'fraud_history': 'Trump Organization fraud conviction 2022',
        'fact_check_history': 'Extensive record of false and misleading statements',
        'credibility_notes': 'Known for frequent false claims and exaggerations'
    },
    'j.d. vance': {
        'full_name': 'James David Vance',
        'role': 'Vice President of the United States',
        'party': 'Republican',
        'criminal_record': None,
        'fraud_history': None,
        'fact_check_history': 'Mixed record on factual accuracy',
        'credibility_notes': 'Serving as VP since January 2025'
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
        
        # Store job in MongoDB
        jobs_collection.insert_one({
            'job_id': job_id,
            **job_data
        })
        
        # Process transcript
        try:
            # Step 1: Process transcript (20%)
            update_job_progress(job_id, 20, 'Processing transcript...')
            processed_transcript = transcript_processor.process(transcript)
            
            # Step 2: Extract metadata
            metadata = transcript_processor.extract_metadata(processed_transcript)
            
            # Step 3: Extract claims (40%)
            update_job_progress(job_id, 40, 'Extracting claims...')
            claims = claim_extractor.extract(processed_transcript)
            
            if not claims:
                update_job_progress(job_id, 100, 'No verifiable claims found')
                results = {
                    'job_id': job_id,
                    'status': 'completed',
                    'claims': [],
                    'fact_checks': [],
                    'credibility_score': 100,
                    'credibility_label': 'No Claims to Verify',
                    'source': source,
                    'metadata': metadata
                }
                jobs_collection.update_one(
                    {'job_id': job_id},
                    {'$set': results}
                )
                return jsonify({'success': True, 'job_id': job_id})
            
            # Step 4: Fact check claims (60-90%)
            update_job_progress(job_id, 60, 'Fact-checking claims...')
            fact_checks = []
            
            for i, claim in enumerate(claims):
                progress = 60 + (30 * i / len(claims))
                update_job_progress(job_id, progress, f'Fact-checking claim {i+1} of {len(claims)}...')
                
                # Enhanced fact checking with better context
                fact_check_result = fact_checker.check_claim(claim, metadata)
                fact_checks.append(fact_check_result)
            
            # Step 5: Calculate credibility score (95%)
            update_job_progress(job_id, 95, 'Calculating credibility score...')
            credibility_data = calculate_credibility_score(fact_checks)
            
            # Step 6: Complete (100%)
            update_job_progress(job_id, 100, 'Analysis complete')
            
            # Get speaker context from metadata or claims
            speaker = None
            if metadata.get('speakers'):
                speaker = metadata['speakers'][0] if metadata['speakers'] else None
            
            # Look up speaker in database
            speaker_context = {}
            if speaker:
                speaker_lower = speaker.lower()
                for key, value in SPEAKER_DATABASE.items():
                    if key in speaker_lower or speaker_lower in key:
                        speaker_context = value.copy()
                        speaker_context['speaker'] = speaker
                        break
            
            # Prepare results
            results = {
                'job_id': job_id,
                'status': 'completed',
                'claims': claims,
                'fact_checks': fact_checks,
                'credibility_score': credibility_data['score'],
                'credibility_label': credibility_data['label'],
                'true_claims': credibility_data['true_claims'],
                'false_claims': credibility_data['false_claims'],
                'unverified_claims': credibility_data['unverified_claims'],
                'total_claims': len(claims),
                'source': source,
                'metadata': metadata,
                'speaker_context': speaker_context,
                'completed_at': datetime.now().isoformat()
            }
            
            # Store results
            jobs_collection.update_one(
                {'job_id': job_id},
                {'$set': results}
            )
            
            return jsonify({'success': True, 'job_id': job_id})
            
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            update_job_progress(job_id, -1, f'Error: {str(e)}')
            jobs_collection.update_one(
                {'job_id': job_id},
                {'$set': {'status': 'failed', 'error': str(e)}}
            )
            return jsonify({'success': False, 'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    try:
        job = jobs_collection.find_one({'job_id': job_id})
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Remove MongoDB _id field
        job.pop('_id', None)
        
        return jsonify({
            'success': True,
            'status': job.get('status'),
            'progress': job.get('progress', 0),
            'message': job.get('message', ''),
            'error': job.get('error')
        })
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get analysis results"""
    try:
        results = jobs_collection.find_one({'job_id': job_id})
        if not results:
            return jsonify({'success': False, 'error': 'Results not found'}), 404
        
        if results.get('status') != 'completed':
            return jsonify({'success': False, 'error': 'Analysis not completed'}), 400
        
        # Remove MongoDB _id field
        results.pop('_id', None)
        
        # Ensure all required fields
        results['success'] = True
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Results retrieval error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/<job_id>/pdf')
def export_pdf(job_id):
    """Export fact-check results as PDF"""
    try:
        # Get job results
        results = jobs_collection.find_one({'job_id': job_id})
        if not results or results['status'] != 'completed':
            return jsonify({'success': False, 'error': 'Results not found or not ready'}), 404
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12
        )
        
        # Title
        elements.append(Paragraph("Transcript Fact Check Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Date
        date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        elements.append(Paragraph(f"Generated on {date_str}", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Summary Section
        elements.append(Paragraph("Executive Summary", heading_style))
        
        # Credibility Score
        credibility = results.get('credibility_score', 0)
        credibility_label = results.get('credibility_label', 'Unknown')
        elements.append(Paragraph(f"<b>Overall Credibility Score:</b> {credibility}% ({credibility_label})", styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Stats table
        stats_data = [
            ['Metric', 'Count'],
            ['Total Claims', str(results.get('total_claims', 0))],
            ['Verified True', str(results.get('true_claims', 0))],
            ['Verified False', str(results.get('false_claims', 0))],
            ['Unverified', str(results.get('unverified_claims', 0))]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb'))
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Speaker Context if available
        speaker_context = results.get('speaker_context', {})
        if speaker_context and speaker_context.get('speaker'):
            elements.append(Paragraph("Speaker Information", heading_style))
            speaker_info = f"<b>Speaker:</b> {speaker_context.get('speaker', 'Unknown')}<br/>"
            if speaker_context.get('role'):
                speaker_info += f"<b>Role:</b> {speaker_context.get('role')}<br/>"
            if speaker_context.get('credibility_notes'):
                speaker_info += f"<b>Notes:</b> {speaker_context.get('credibility_notes')}"
            elements.append(Paragraph(speaker_info, styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
        
        # Detailed Fact Checks
        elements.append(PageBreak())
        elements.append(Paragraph("Detailed Fact Checks", heading_style))
        elements.append(Spacer(1, 0.2*inch))
        
        fact_checks = results.get('fact_checks', [])
        for i, check in enumerate(fact_checks, 1):
            # Claim header
            verdict = check.get('verdict', 'unverified')
            verdict_color = {
                'true': '#10b981',
                'false': '#ef4444',
                'unverified': '#f59e0b',
                'misleading': '#dc2626',
                'mixed': '#8b5cf6'
            }.get(verdict.lower(), '#6b7280')
            
            claim_style = ParagraphStyle(
                'Claim',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#1f2937'),
                spaceAfter=6,
                leftIndent=0
            )
            
            elements.append(Paragraph(f"<b>Claim {i}:</b> {check.get('claim', 'N/A')}", claim_style))
            
            # Verdict
            verdict_text = f"<font color='{verdict_color}'><b>Verdict: {verdict.upper()}</b></font>"
            elements.append(Paragraph(verdict_text, styles['Normal']))
            
            # Explanation
            if check.get('explanation'):
                elements.append(Paragraph(f"<b>Explanation:</b> {check.get('explanation')}", styles['Normal']))
            
            # Sources
            if check.get('sources'):
                sources_text = "<b>Sources:</b><br/>"
                for source in check.get('sources', []):
                    sources_text += f"• {source}<br/>"
                elements.append(Paragraph(sources_text, styles['Normal']))
            
            # Confidence
            if check.get('confidence'):
                elements.append(Paragraph(f"<b>Confidence:</b> {check.get('confidence')}%", styles['Normal']))
            
            elements.append(Spacer(1, 0.3*inch))
            
            # Add a separator line between claims
            if i < len(fact_checks):
                elements.append(Paragraph("<hr/>", styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
        
        # Footer
        elements.append(PageBreak())
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER
        )
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("Generated by Transcript Fact Checker", footer_style))
        elements.append(Paragraph("Powered by Google Fact Check API and Advanced NLP", footer_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Return PDF
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'fact-check-report-{job_id}.pdf'
        )
        
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper functions
def update_job_progress(job_id, progress, message):
    """Update job progress in database"""
    jobs_collection.update_one(
        {'job_id': job_id},
        {'$set': {
            'progress': progress,
            'message': message,
            'updated_at': datetime.now().isoformat()
        }}
    )

def calculate_credibility_score(fact_checks):
    """Calculate overall credibility score from fact checks"""
    if not fact_checks:
        return {
            'score': 100,
            'label': 'No Claims to Verify',
            'true_claims': 0,
            'false_claims': 0,
            'unverified_claims': 0
        }
    
    true_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['true', 'mostly true'])
    false_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['false', 'mostly false', 'misleading', 'deceptive'])
    mixed_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() == 'mixed')
    unverified_count = sum(1 for fc in fact_checks if fc.get('verdict', '').lower() in ['unverified', 'unsubstantiated', 'lacks_context'])
    
    total = len(fact_checks)
    
    # Calculate weighted score
    score = ((true_count * 100) + (mixed_count * 50) + (unverified_count * 30)) / total
    
    # Determine label
    if score >= 80:
        label = 'High Credibility'
    elif score >= 60:
        label = 'Moderate Credibility'
    elif score >= 40:
        label = 'Low Credibility'
    else:
        label = 'Very Low Credibility'
    
    return {
        'score': round(score),
        'label': label,
        'true_claims': true_count,
        'false_claims': false_count,
        'unverified_claims': unverified_count
    }

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)
