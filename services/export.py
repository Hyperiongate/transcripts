"""
PDF Export Service for Transcript Fact Checker
Generates professional PDF reports with conversational summaries
"""
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus.flowables import HRFlowable
import logging

logger = logging.getLogger(__name__)

class PDFExporter:
    """Generate professional PDF fact-check reports"""
    
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
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Conversational style
        self.styles.add(ParagraphStyle(
            name='Conversational',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#374151'),
            alignment=TA_JUSTIFY,
            spaceAfter=12
        ))
        
        # Claim style
        self.styles.add(ParagraphStyle(
            name='Claim',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#1f2937'),
            leftIndent=20,
            rightIndent=20,
            spaceBefore=6,
            spaceAfter=6,
            borderWidth=1,
            borderColor=colors.HexColor('#e5e7eb'),
            borderPadding=10,
            backColor=colors.HexColor('#f9fafb')
        ))
        
        # Verdict styles
        self.styles.add(ParagraphStyle(
            name='VerdictTrue',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#10b981'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='VerdictFalse',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#ef4444'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='VerdictMixed',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#8b5cf6'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
    
    def generate_report(self, results, output_path):
        """Generate complete PDF report"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Build the story
        story = []
        
        # Title page
        story.extend(self._create_title_page(results))
        
        # Overall Assessment - NEW SECTION
        story.extend(self._create_overall_assessment(results))
        
        # Speaker history analysis
        if results.get('speaker') and results.get('speaker_history'):
            story.extend(self._create_speaker_history(results['speaker'], results['speaker_history']))
        
        # Deception Pattern Analysis
        story.extend(self._create_deception_analysis(results))
        
        # Detailed fact checks
        story.extend(self._create_fact_checks(results))
        
        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path
    
    def _create_title_page(self, results):
        """Create title page elements"""
        elements = []
        
        # Title
        elements.append(Paragraph(
            "Transcript Fact-Check Report",
            self.styles['CustomTitle']
        ))
        
        # Subtitle with source
        elements.append(Paragraph(
            f"Analysis of: {results.get('source', 'Unknown Source')}",
            self.styles['Subtitle']
        ))
        
        # Date
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            self.styles['Normal']
        ))
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Credibility score visualization
        elements.append(self._create_credibility_visual(results['credibility_score']))
        
        elements.append(PageBreak())
        
        return elements
    
    def _create_overall_assessment(self, results):
        """Create overall assessment section"""
        elements = []
        
        elements.append(Paragraph("Overall Assessment", self.styles['SectionHeader']))
        
        # Use conversational summary if available
        if results.get('conversational_summary'):
            elements.append(Paragraph(results['conversational_summary'], self.styles['Conversational']))
        else:
            # Generate one if not available
            summary_text = self._generate_assessment(results)
            elements.append(Paragraph(summary_text, self.styles['Conversational']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Key statistics table
        elements.append(self._create_stats_table(results))
        
        elements.append(Spacer(1, 0.5*inch))
        
        return elements
    
    def _generate_assessment(self, results):
        """Generate assessment if conversational summary not available"""
        score = results['credibility_score']
        total_claims = results['checked_claims']
        
        # Get verdict counts
        verdicts = [fc['verdict'] for fc in results['fact_checks']]
        false_count = sum(1 for v in verdicts if v in ['false', 'mostly_false'])
        deceptive_count = sum(1 for v in verdicts if v in ['deceptive', 'misleading'])
        lacks_context_count = sum(1 for v in verdicts if v == 'lacks_context')
        
        # Opening based on credibility score
        if score >= 80:
            assessment = "This transcript demonstrates high overall credibility. "
        elif score >= 60:
            assessment = "This transcript shows moderate credibility with some significant concerns. "
        elif score >= 40:
            assessment = "This transcript has serious credibility issues that warrant careful scrutiny. "
        else:
            assessment = "This transcript exhibits very low credibility with numerous problematic claims. "
        
        # Details about claims
        assessment += f"\n\nWe analyzed {total_claims} factual claims in this transcript. "
        
        if false_count > 0:
            assessment += f"{false_count} were demonstrably false. "
        
        if deceptive_count > 0:
            assessment += (f"{deceptive_count} used true facts in deliberately deceptive ways - "
                          f"this is not simply misspeaking but appears to be intentional manipulation. ")
        
        if lacks_context_count > 0:
            assessment += (f"{lacks_context_count} omitted critical context that would change "
                          f"how listeners understand the claim. ")
        
        # Pattern assessment
        if deceptive_count >= 3 or (deceptive_count + lacks_context_count) >= 5:
            assessment += ("\n\nThe pattern of deceptive statements and strategic omissions suggests "
                          "this is not accidental but a deliberate communication strategy designed to mislead.")
        
        return assessment
    
    def _create_speaker_history(self, speaker_name, history):
        """Create speaker history section"""
        elements = []
        
        elements.append(Paragraph(f"Speaker Profile: {speaker_name}", self.styles['SectionHeader']))
        
        # Historical overview
        overview = (f"This analysis adds to our growing understanding of {speaker_name}'s "
                   f"communication patterns. Over {history['total_analyses']} analyses, "
                   f"we've tracked {history['total_claims']} factual claims.")
        elements.append(Paragraph(overview, self.styles['Conversational']))
        
        # Credibility trend
        avg_cred = history['average_credibility']
        recent_cred = history.get('recent_credibility', avg_cred)
        
        if abs(recent_cred - avg_cred) > 10:
            if recent_cred < avg_cred:
                trend = (f"\n\nConcerningly, their credibility has been declining. "
                        f"Their recent average ({recent_cred:.0f}%) is significantly lower "
                        f"than their historical average ({avg_cred:.0f}%).")
            else:
                trend = (f"\n\nEncouragingly, their credibility has been improving. "
                        f"Their recent average ({recent_cred:.0f}%) is higher "
                        f"than their historical average ({avg_cred:.0f}%).")
            elements.append(Paragraph(trend, self.styles['Conversational']))
        
        # Pattern analysis
        if history['total_false_claims'] > 0 or history['total_misleading_claims'] > 0:
            false_rate = history.get('false_claim_rate', 0)
            pattern_text = f"\n\nHistorical Pattern Analysis:"
            elements.append(Paragraph(pattern_text, self.styles['Heading3']))
            
            stats = []
            stats.append(f"• Total false claims: {history['total_false_claims']} ({false_rate:.1%} of all claims)")
            stats.append(f"• Deliberately deceptive claims: {history['total_misleading_claims']}")
            
            for stat in stats:
                elements.append(Paragraph(stat, self.styles['Normal']))
        
        # Notable patterns
        if history.get('patterns'):
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("Identified Patterns:", self.styles['Heading3']))
            for pattern in history['patterns']:
                elements.append(Paragraph(f"• {pattern}", self.styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _create_deception_analysis(self, results):
        """Create deception pattern analysis"""
        elements = []
        
        # Analyze deception patterns
        from services.verdict_definitions import VerdictDefinitions
        verdicts = [fc['verdict'] for fc in results['fact_checks']]
        deception_analysis = VerdictDefinitions.get_deception_analysis(verdicts)
        
        if deception_analysis['deception_pattern'] != 'No deception detected':
            elements.append(Paragraph("Deception Analysis", self.styles['SectionHeader']))
            
            # Main pattern
            pattern_text = (f"Pattern Identified: {deception_analysis['deception_pattern']}\n\n"
                           f"This transcript contains {deception_analysis['deceptive_statements']} "
                           f"deliberately deceptive statements, {deception_analysis['context_omissions']} "
                           f"critical context omissions, and {deception_analysis['false_statements']} "
                           f"outright false claims.")
            
            elements.append(Paragraph(pattern_text, self.styles['Conversational']))
            
            # Interpretation
            if deception_analysis['deceptive_statements'] >= 3:
                interpretation = ("\n\nThe repeated use of technically true statements presented in "
                                "deliberately misleading ways indicates sophisticated deception. This is "
                                "not simply getting facts wrong - it's using facts as weapons of misinformation.")
                elements.append(Paragraph(interpretation, self.styles['Conversational']))
            
            elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _create_fact_checks(self, results):
        """Create detailed fact checks section"""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph("Detailed Fact Checks", self.styles['SectionHeader']))
        
        for i, check in enumerate(results['fact_checks'], 1):
            # Claim header
            verdict_style = self._get_verdict_style(check['verdict'])
            
            # Full claim context
            elements.append(Paragraph(f"Claim #{i}", self.styles['Heading3']))
            
            # Show full context if available
            if check.get('full_context'):
                elements.append(Paragraph(
                    f'"{check["full_context"]}"',
                    self.styles['Claim']
                ))
            else:
                elements.append(Paragraph(
                    f'"{check["claim"]}"',
                    self.styles['Claim']
                ))
            
            # Verdict with updated language
            verdict_label = check['verdict'].replace('misleading', 'deceptive').replace('_', ' ').title()
            elements.append(Paragraph(
                f"Verdict: {verdict_label}",
                verdict_style
            ))
            
            # Explanation
            elements.append(Paragraph(check['explanation'], self.styles['Normal']))
            
            # Sources
            if check.get('sources'):
                elements.append(Paragraph("Sources:", self.styles['Heading4']))
                for source in check['sources']:
                    elements.append(Paragraph(f"• {source}", self.styles['Normal']))
            
            elements.append(HRFlowable(width="80%", thickness=1, 
                                     color=colors.HexColor('#e5e7eb'),
                                     spaceBefore=12, spaceAfter=12))
        
        return elements
    
    def _create_credibility_visual(self, score):
        """Create visual representation of credibility score"""
        # Create a simple table-based visualization
        data = [['Credibility Score'], [f'{score}%']]
        
        # Color based on score
        if score >= 80:
            bg_color = colors.HexColor('#10b981')
        elif score >= 60:
            bg_color = colors.HexColor('#fbbf24')
        elif score >= 40:
            bg_color = colors.HexColor('#f59e0b')
        else:
            bg_color = colors.HexColor('#ef4444')
        
        t = Table(data, colWidths=[4*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 14),
            ('FONTSIZE', (0, 1), (0, 1), 36),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [bg_color, bg_color]),
        ]))
        
        return t
    
    def _create_stats_table(self, results):
        """Create statistics table"""
        data = [
            ['Metric', 'Value'],
            ['Total Claims Analyzed', str(results['checked_claims'])],
            ['Verified True', str(sum(1 for fc in results['fact_checks'] 
                                    if fc.get('verdict') in ['true', 'mostly_true']))],
            ['Found False', str(sum(1 for fc in results['fact_checks'] 
                                  if fc.get('verdict') in ['false', 'mostly_false']))],
            ['Deliberately Deceptive', str(sum(1 for fc in results['fact_checks'] 
                                 if fc.get('verdict') in ['deceptive', 'misleading']))],
            ['Missing Critical Context', str(sum(1 for fc in results['fact_checks'] 
                                 if fc.get('verdict') == 'lacks_context'))],
            ['Unverified', str(sum(1 for fc in results['fact_checks'] 
                                 if fc.get('verdict') == 'unverified'))],
        ]
        
        t = Table(data, colWidths=[3*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ]))
        
        return t
    
    def _get_verdict_style(self, verdict):
        """Get appropriate style for verdict"""
        if verdict in ['true', 'mostly_true']:
            return self.styles['VerdictTrue']
        elif verdict in ['false', 'mostly_false']:
            return self.styles['VerdictFalse']
        else:
            return self.styles['VerdictMixed']
