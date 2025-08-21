"""
Export Service - PDF Generation for Fact Check Reports
"""
import os
import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, red, green, orange, gray
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

logger = logging.getLogger(__name__)

class PDFExporter:
    """Generate professional PDF reports for fact check results"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
        
    def _create_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section headers
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Executive Summary style
        self.styles.add(ParagraphStyle(
            name='ExecutiveSummary',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=18,
            spaceAfter=12,
            borderWidth=2,
            borderColor=HexColor('#e5e7eb'),
            borderPadding=10,
            backColor=HexColor('#f9fafb')
        ))
        
        # Verdict styles
        self.styles.add(ParagraphStyle(
            name='VerdictTrue',
            parent=self.styles['Normal'],
            textColor=HexColor('#10b981'),
            fontSize=11,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='VerdictFalse', 
            parent=self.styles['Normal'],
            textColor=HexColor('#ef4444'),
            fontSize=11,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='VerdictMixed',
            parent=self.styles['Normal'],
            textColor=HexColor('#f59e0b'),
            fontSize=11,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='VerdictDeceptive',
            parent=self.styles['Normal'],
            textColor=HexColor('#dc2626'),
            fontSize=11,
            fontName='Helvetica-Bold'
        ))
    
    def export_to_pdf(self, results: dict) -> str:
        """Export results to PDF and return the file path"""
        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = results.get('job_id', 'unknown')
        output_filename = f"fact_check_{job_id}_{timestamp}.pdf"
        output_path = os.path.join('exports', output_filename)
        
        # Create exports directory if it doesn't exist
        os.makedirs('exports', exist_ok=True)
        
        # Generate PDF
        if self.generate_pdf(results, output_path):
            return output_path
        else:
            raise Exception("Failed to generate PDF")
    
    def generate_pdf(self, results: dict, output_path: str) -> bool:
        """Generate PDF report from fact check results"""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build content
            story = []
            
            # Title page
            story.append(Paragraph("Transcript Fact Check Report", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            # Report metadata
            metadata = f"""
            <para align=center>
            <b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
            <b>Source:</b> {results.get('source_type', 'Unknown')}<br/>
            <b>Total Claims:</b> {results.get('total_claims', 0)}<br/>
            <b>Checked Claims:</b> {results.get('checked_claims', 0)}
            </para>
            """
            story.append(Paragraph(metadata, self.styles['Normal']))
            story.append(Spacer(1, 0.5*inch))
            
            # Enhanced Conversational Summary
            if results.get('enhanced_summary'):
                story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
                # Handle multi-line summary with proper formatting
                summary_text = self._escape_html(results['enhanced_summary'])
                summary_text = summary_text.replace('\n', '<br/>')
                story.append(Paragraph(summary_text, self.styles['Normal']))
                story.append(Spacer(1, 0.3*inch))
            elif results.get('summary'):
                story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
                summary_text = self._escape_html(results['summary'])
                summary_text = summary_text.replace('\n', '<br/>')
                story.append(Paragraph(summary_text, self.styles['Normal']))
                story.append(Spacer(1, 0.3*inch))
            
            # Speaker Information
            if results.get('speakers') and len(results['speakers']) > 0:
                story.append(Paragraph("Speaker Information", self.styles['SectionHeader']))
                
                for speaker_name, speaker_info in results['speakers'].items():
                    story.append(Paragraph(f"<b>{speaker_name}</b>", self.styles['Normal']))
                    
                    if speaker_info.get('criminal_record'):
                        story.append(Paragraph(f"Criminal Record: {speaker_info['criminal_record']}", self.styles['Normal']))
                    if speaker_info.get('fraud_history'):
                        story.append(Paragraph(f"Fraud History: {speaker_info['fraud_history']}", self.styles['Normal']))
                    if speaker_info.get('fact_check_history'):
                        history = speaker_info['fact_check_history']
                        story.append(Paragraph(f"Past Fact Checks: {history.get('total_claims', 0)} claims, {history.get('accuracy_rate', 0):.1f}% accurate", self.styles['Normal']))
                    
                    story.append(Spacer(1, 0.2*inch))
                
                story.append(Spacer(1, 0.3*inch))
            
            # Statistics Overview
            story.append(Paragraph("Analysis Overview", self.styles['SectionHeader']))
            
            # Count verdicts
            verdict_counts = self._count_verdicts(results.get('fact_checks', []))
            
            stats_data = [
                ['Metric', 'Value'],
                ['Total Claims Identified', str(results.get('total_claims', 0))],
                ['Claims Fact-Checked', str(results.get('checked_claims', 0))],
                ['True/Mostly True', str(verdict_counts.get('true', 0))],
                ['Nearly True', str(verdict_counts.get('nearly_true', 0))],
                ['Exaggeration', str(verdict_counts.get('exaggeration', 0))],
                ['Misleading', str(verdict_counts.get('misleading', 0))],
                ['Mostly False', str(verdict_counts.get('mostly_false', 0))],
                ['False', str(verdict_counts.get('false', 0))],
                ['Intentionally Deceptive', str(verdict_counts.get('intentionally_deceptive', 0))],
                ['Needs Context', str(verdict_counts.get('needs_context', 0))],
                ['Opinion', str(verdict_counts.get('opinion', 0))],
                ['Unverified', str(verdict_counts.get('unverified', 0))]
            ]
            
            stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f9fafb')),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb'))
            ]))
            
            story.append(stats_table)
            story.append(PageBreak())
            
            # Detailed Fact Checks
            story.append(Paragraph("Detailed Fact Check Results", self.styles['SectionHeader']))
            story.append(Spacer(1, 0.2*inch))
            
            for i, fc in enumerate(results.get('fact_checks', []), 1):
                # Claim header - show full context
                claim_text = fc.get('full_context') or fc.get('claim', 'No claim text')
                claim_header = f"<b>Claim {i}:</b> {self._escape_html(claim_text)}"
                story.append(Paragraph(claim_header, self.styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                # Verdict
                verdict = fc.get('verdict', 'unverified')
                verdict_style = self._get_verdict_style(verdict)
                verdict_text = f"<b>Verdict:</b> {verdict.replace('_', ' ').title()}"
                story.append(Paragraph(verdict_text, verdict_style))
                
                # Confidence
                if fc.get('confidence'):
                    conf_text = f"<b>Confidence:</b> {fc['confidence']}%"
                    story.append(Paragraph(conf_text, self.styles['Normal']))
                
                # Explanation
                if fc.get('explanation'):
                    story.append(Paragraph("<b>Explanation:</b>", self.styles['Normal']))
                    explanation_text = self._escape_html(fc['explanation'])
                    story.append(Paragraph(explanation_text, self.styles['Normal']))
                
                # Sources
                if fc.get('sources'):
                    sources_text = f"<b>Sources:</b> {', '.join(fc['sources'])}"
                    story.append(Paragraph(sources_text, self.styles['Normal']))
                
                # AI Analysis flag
                if fc.get('ai_analysis_used'):
                    story.append(Paragraph("<i>✓ AI-enhanced analysis</i>", self.styles['Normal']))
                
                story.append(Spacer(1, 0.3*inch))
                
                # Add page break every 3 claims to maintain readability
                if i % 3 == 0 and i < len(results.get('fact_checks', [])):
                    story.append(PageBreak())
            
            # Build PDF
            doc.build(story)
            return True
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return False
    
    def _count_verdicts(self, fact_checks: list) -> dict:
        """Count verdicts by type"""
        counts = {
            'true': 0,
            'mostly_true': 0,
            'nearly_true': 0,
            'exaggeration': 0,
            'misleading': 0,
            'mostly_false': 0,
            'false': 0,
            'intentionally_deceptive': 0,
            'needs_context': 0,
            'opinion': 0,
            'unverified': 0
        }
        
        for fc in fact_checks:
            verdict = fc.get('verdict', 'unverified').lower()
            if verdict in ['true', 'mostly_true']:
                counts['true'] += 1
            elif verdict in counts:
                counts[verdict] += 1
            else:
                counts['unverified'] += 1
        
        return counts
    
    def _get_verdict_style(self, verdict: str):
        """Get appropriate style for verdict"""
        verdict_lower = verdict.lower()
        if verdict_lower in ['true', 'mostly_true', 'nearly_true']:
            return self.styles['VerdictTrue']
        elif verdict_lower in ['false', 'mostly_false']:
            return self.styles['VerdictFalse']
        elif verdict_lower in ['misleading', 'intentionally_deceptive']:
            return self.styles['VerdictDeceptive']
        else:
            return self.styles['VerdictMixed']
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters for ReportLab"""
        if not text:
            return ''
        return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))
