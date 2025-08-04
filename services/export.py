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
            <b>Source:</b> {results.get('source', 'Unknown')}<br/>
            <b>Credibility Score:</b> {results.get('credibility_score', 0)}% ({results.get('credibility_label', 'Unknown')})
            </para>
            """
            story.append(Paragraph(metadata, self.styles['Normal']))
            story.append(Spacer(1, 0.5*inch))
            
            # Executive Summary (if available)
            if results.get('executive_summary'):
                story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
                story.append(Paragraph(results['executive_summary'], self.styles['ExecutiveSummary']))
                story.append(Spacer(1, 0.3*inch))
            
            # Speaker Analysis (if available)
            if results.get('speaker_analysis'):
                story.append(Paragraph("Speaker Analysis", self.styles['SectionHeader']))
                speaker_info = results['speaker_analysis']
                
                if speaker_info.get('main_speaker'):
                    story.append(Paragraph(f"<b>Primary Speaker:</b> {speaker_info['main_speaker']}", self.styles['Normal']))
                
                if speaker_info.get('background'):
                    story.append(Paragraph("<b>Background Information:</b>", self.styles['Normal']))
                    story.append(Paragraph(speaker_info['background'], self.styles['Normal']))
                
                if speaker_info.get('credibility_history'):
                    story.append(Paragraph("<b>Credibility History:</b>", self.styles['Normal']))
                    story.append(Paragraph(speaker_info['credibility_history'], self.styles['Normal']))
                
                if speaker_info.get('controversies'):
                    story.append(Paragraph("<b>Notable Controversies:</b>", self.styles['Normal']))
                    story.append(Paragraph(speaker_info['controversies'], self.styles['Normal']))
                
                story.append(Spacer(1, 0.3*inch))
            
            # Statistics Overview
            story.append(Paragraph("Analysis Overview", self.styles['SectionHeader']))
            
            stats_data = [
                ['Metric', 'Value'],
                ['Total Claims Identified', str(results.get('total_claims', 0))],
                ['Claims Fact-Checked', str(results.get('checked_claims', 0))],
                ['Verified as True', str(sum(1 for fc in results.get('fact_checks', []) if fc.get('verdict') in ['true', 'mostly_true']))],
                ['Found False', str(sum(1 for fc in results.get('fact_checks', []) if fc.get('verdict') in ['false', 'mostly_false']))],
                ['Unverified', str(sum(1 for fc in results.get('fact_checks', []) if fc.get('verdict') == 'unverified'))],
                ['Overall Credibility', f"{results.get('credibility_score', 0)}%"]
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
                # Claim header
                claim_text = f"<b>Claim {i}:</b> {fc.get('claim', 'No claim text')}"
                story.append(Paragraph(claim_text, self.styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                # Verdict
                verdict = fc.get('verdict', 'unverified')
                verdict_style = self._get_verdict_style(verdict)
                verdict_text = f"<b>Verdict:</b> {verdict.upper()}"
                story.append(Paragraph(verdict_text, verdict_style))
                
                # Confidence
                if fc.get('confidence'):
                    conf_text = f"<b>Confidence:</b> {fc['confidence']}%"
                    story.append(Paragraph(conf_text, self.styles['Normal']))
                
                # Explanation
                if fc.get('explanation'):
                    story.append(Paragraph("<b>Explanation:</b>", self.styles['Normal']))
                    story.append(Paragraph(fc['explanation'], self.styles['Normal']))
                
                # Sources
                if fc.get('sources'):
                    sources_text = f"<b>Sources:</b> {', '.join(fc['sources'])}"
                    story.append(Paragraph(sources_text, self.styles['Normal']))
                
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
    
    def _get_verdict_style(self, verdict: str):
        """Get appropriate style for verdict"""
        verdict_lower = verdict.lower()
        if verdict_lower in ['true', 'mostly_true']:
            return self.styles['VerdictTrue']
        elif verdict_lower in ['false', 'mostly_false']:
            return self.styles['VerdictFalse']
        else:
            return self.styles['VerdictMixed']
