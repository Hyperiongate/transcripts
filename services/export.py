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

class ExportService:
    """Main export service that handles multiple export formats"""
    
    def __init__(self):
        self.pdf_exporter = PDFExporter()
    
    def export_pdf(self, results: dict, job_id: str) -> str:
        """Export results to PDF format - interface expected by app.py"""
        # Add job_id to results for filename generation
        results_with_id = results.copy()
        results_with_id['job_id'] = job_id
        return self.pdf_exporter.export_to_pdf(results_with_id)

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
            <b>Checked Claims:</b> {len(results.get('fact_checks', []))}
            </para>
            """
            story.append(Paragraph(metadata, self.styles['Normal']))
            story.append(Spacer(1, 0.5*inch))
            
            # Summary section - handle both summary formats
            if results.get('summary'):
                story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
                # Convert markdown-style formatting to basic HTML for ReportLab
                summary_text = self._convert_markdown_to_html(results['summary'])
                story.append(Paragraph(summary_text, self.styles['Normal']))
                story.append(Spacer(1, 0.3*inch))
            
            # Credibility Score section
            credibility_score = results.get('credibility_score', {})
            if credibility_score:
                story.append(Paragraph("Credibility Analysis", self.styles['SectionHeader']))
                
                score = credibility_score.get('score', 'N/A')
                label = credibility_score.get('label', 'Unknown')
                story.append(Paragraph(f"<b>Overall Score:</b> {score}/100", self.styles['Normal']))
                story.append(Paragraph(f"<b>Assessment:</b> {label}", self.styles['Normal']))
                
                # Breakdown
                breakdown = credibility_score.get('breakdown', {})
                if breakdown:
                    story.append(Paragraph("<b>Claims Breakdown:</b>", self.styles['Normal']))
                    for category, count in breakdown.items():
                        if count > 0:
                            readable_category = category.replace('_', ' ').title()
                            story.append(Paragraph(f"  • {readable_category}: {count}", self.styles['Normal']))
                
                story.append(Spacer(1, 0.3*inch))
            
            # Speaker Information
            speakers = results.get('speakers', [])
            if speakers and len(speakers) > 0:
                story.append(Paragraph("Speakers Analyzed", self.styles['SectionHeader']))
                if isinstance(speakers, list):
                    for speaker in speakers:
                        story.append(Paragraph(f"• {speaker}", self.styles['Normal']))
                else:
                    # Handle case where speakers might be a different format
                    story.append(Paragraph(f"• {str(speakers)}", self.styles['Normal']))
                story.append(Spacer(1, 0.3*inch))
            
            # Statistics Overview
            story.append(Paragraph("Analysis Overview", self.styles['SectionHeader']))
            
            # Count verdicts from fact_checks
            fact_checks = results.get('fact_checks', [])
            verdict_counts = self._count_verdicts(fact_checks)
            
            stats_data = [
                ['Verdict Type', 'Count'],
                ['True/Mostly True', str(verdict_counts.get('true', 0))],
                ['Nearly True', str(verdict_counts.get('nearly_true', 0))],
                ['Partially Accurate', str(verdict_counts.get('partially_accurate', 0))],
                ['Exaggeration', str(verdict_counts.get('exaggeration', 0))],
                ['Misleading', str(verdict_counts.get('misleading', 0))],
                ['Mostly False', str(verdict_counts.get('mostly_false', 0))],
                ['False', str(verdict_counts.get('false', 0))],
                ['Empty Rhetoric', str(verdict_counts.get('empty_rhetoric', 0))],
                ['Needs Context', str(verdict_counts.get('needs_context', 0))],
                ['Opinion', str(verdict_counts.get('opinion', 0))],
                ['Unverifiable', str(verdict_counts.get('unverifiable', 0))]
            ]
            
            # Filter out rows with zero counts for cleaner display
            stats_data = [stats_data[0]] + [row for row in stats_data[1:] if int(row[1]) > 0]
            
            if len(stats_data) > 1:  # Only show table if there are results
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
            if fact_checks:
                story.append(Paragraph("Detailed Fact Check Results", self.styles['SectionHeader']))
                story.append(Spacer(1, 0.2*inch))
                
                for i, fc in enumerate(fact_checks, 1):
                    if fc is None:  # Skip None results
                        continue
                        
                    # Claim header
                    claim_text = fc.get('claim', 'No claim text')
                    claim_header = f"<b>Claim {i}:</b> {self._escape_html(claim_text)}"
                    story.append(Paragraph(claim_header, self.styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
                    
                    # Speaker
                    speaker = fc.get('speaker', 'Unknown')
                    if speaker != 'Unknown':
                        story.append(Paragraph(f"<b>Speaker:</b> {speaker}", self.styles['Normal']))
                    
                    # Verdict
                    verdict = fc.get('verdict', 'unverifiable')
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
                    
                    story.append(Spacer(1, 0.3*inch))
                    
                    # Add page break every 3 claims to maintain readability
                    if i % 3 == 0 and i < len(fact_checks):
                        story.append(PageBreak())
            
            # Build PDF
            doc.build(story)
            return True
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return False
    
    def _convert_markdown_to_html(self, text: str) -> str:
        """Convert basic markdown to HTML for ReportLab"""
        if not text:
            return ''
        
        # Convert markdown to basic HTML
        html_text = str(text)
        
        # Convert headers
        html_text = html_text.replace('### ', '<b>').replace('## ', '<b>').replace('# ', '<b>')
        
        # Add closing bold tags after line breaks for headers
        lines = html_text.split('\n')
        processed_lines = []
        for line in lines:
            if line.startswith('<b>') and not line.endswith('</b>'):
                # Find the end of the header line
                if ':' in line:
                    parts = line.split(':', 1)
                    processed_lines.append(f"{parts[0]}:</b>{parts[1] if len(parts) > 1 else ''}")
                else:
                    processed_lines.append(f"{line}</b>")
            else:
                processed_lines.append(line)
        
        html_text = '\n'.join(processed_lines)
        
        # Convert **bold** to <b>bold</b>
        import re
        html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)
        
        # Convert line breaks to <br/>
        html_text = html_text.replace('\n', '<br/>')
        
        # Escape other HTML
        html_text = self._escape_html_selective(html_text)
        
        return html_text
    
    def _count_verdicts(self, fact_checks: list) -> dict:
        """Count verdicts by type"""
        counts = {
            'true': 0,
            'mostly_true': 0,
            'nearly_true': 0,
            'partially_accurate': 0,
            'exaggeration': 0,
            'misleading': 0,
            'mostly_false': 0,
            'false': 0,
            'empty_rhetoric': 0,
            'unsubstantiated_prediction': 0,
            'pattern_of_false_promises': 0,
            'needs_context': 0,
            'opinion': 0,
            'unverifiable': 0
        }
        
        for fc in fact_checks:
            if fc is None:
                continue
                
            verdict = fc.get('verdict', 'unverifiable').lower()
            if verdict in ['true', 'mostly_true']:
                counts['true'] += 1
            elif verdict in counts:
                counts[verdict] += 1
            else:
                counts['unverifiable'] += 1
        
        return counts
    
    def _get_verdict_style(self, verdict: str):
        """Get appropriate style for verdict"""
        verdict_lower = verdict.lower()
        if verdict_lower in ['true', 'mostly_true', 'nearly_true']:
            return self.styles['VerdictTrue']
        elif verdict_lower in ['false', 'mostly_false']:
            return self.styles['VerdictFalse']
        elif verdict_lower in ['misleading', 'pattern_of_false_promises']:
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
    
    def _escape_html_selective(self, text: str) -> str:
        """Escape HTML but preserve our formatting tags"""
        if not text:
            return ''
        
        # First, protect our tags
        protected_text = (str(text)
            .replace('<b>', '|||BOLD_START|||')
            .replace('</b>', '|||BOLD_END|||')
            .replace('<br/>', '|||BR|||'))
        
        # Escape everything else
        escaped_text = (protected_text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))
        
        # Restore our tags
        final_text = (escaped_text
            .replace('|||BOLD_START|||', '<b>')
            .replace('|||BOLD_END|||', '</b>')
            .replace('|||BR|||', '<br/>'))
        
        return final_text
