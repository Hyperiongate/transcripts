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
        
        # Executive summary with conversational tone
        story.extend(self._create_executive_summary(results))
        
        # Speaker history analysis
        if results.get('speaker_history'):
            story.extend(self._create_speaker_history(results['speaker_history']))
        
        # Detailed fact checks
        story.extend(self._create_fact_checks(results))
        
        # Pattern analysis
        story.extend(self._create_pattern_analysis(results))
        
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
    
    def _create_executive_summary(self, results):
        """Create conversational executive summary"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        # Generate conversational summary
        summary_text = self._generate_conversational_summary(results)
        elements.append(Paragraph(summary_text, self.styles['Conversational']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Key statistics table
        elements.append(self._create_stats_table(results))
        
        elements.append(Spacer(1, 0.5*inch))
        
        return elements
    
    def _generate_conversational_summary(self, results):
        """Generate a natural, conversational summary"""
        score = results['credibility_score']
        total_claims = results['checked_claims']
        false_count = sum(1 for fc in results['fact_checks'] 
                         if fc.get('verdict') in ['false', 'mostly_false'])
        misleading_count = sum(1 for fc in results['fact_checks'] 
                              if fc.get('verdict') == 'misleading')
        
        # Opening based on credibility score
        if score >= 80:
            opening = "The good news is that this transcript appears to be highly credible. "
        elif score >= 60:
            opening = "This transcript shows moderate credibility with some concerns. "
        elif score >= 40:
            opening = "This transcript raises significant credibility concerns. "
        else:
            opening = "This transcript has serious credibility issues that need attention. "
        
        # Details about claims
        details = f"Out of {total_claims} factual claims we examined, "
        
        if false_count == 0 and misleading_count == 0:
            details += "we didn't find any that were outright false or misleading. "
        elif false_count > 0 and misleading_count > 0:
            details += f"we found {false_count} false statements and {misleading_count} misleading claims. "
        elif false_count > 0:
            details += f"we found {false_count} false statements. "
        else:
            details += f"we found {misleading_count} misleading claims. "
        
        # Pattern observations
        if misleading_count >= 3:
            pattern = (f"\n\nOf particular concern is the pattern of misleading statements. "
                      f"While one or two might be inadvertent, {misleading_count} misleading claims "
                      f"suggests a pattern of misrepresentation that readers should be aware of.")
        else:
            pattern = ""
        
        # Context about verification
        context = ("\n\nIt's important to note that not all claims could be independently verified. "
                  "Some statements are matters of opinion or prediction, while others lack sufficient "
                  "public information for fact-checking. We've focused on verifiable factual claims.")
        
        return opening + details + pattern + context
    
    def _create_speaker_history(self, history):
        """Create speaker history section"""
        elements = []
        
        elements.append(Paragraph("Speaker Background & History", self.styles['SectionHeader']))
        
        if history.get('previous_analyses'):
            text = (f"This is not the first time we've analyzed content from this source. "
                   f"Over {history['total_analyses']} previous analyses, we've observed:")
            elements.append(Paragraph(text, self.styles['Conversational']))
            
            # Historical patterns
            history_items = []
            if history.get('average_credibility'):
                history_items.append(f"Average credibility score: {history['average_credibility']:.1f}%")
            if history.get('total_false_claims'):
                history_items.append(f"Total false claims: {history['total_false_claims']}")
            if history.get('total_misleading_claims'):
                history_items.append(f"Total misleading claims: {history['total_misleading_claims']}")
            
            for item in history_items:
                elements.append(Paragraph(f"• {item}", self.styles['Normal']))
        
        # Notable patterns
        if history.get('patterns'):
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("Notable Patterns:", self.styles['Heading3']))
            for pattern in history['patterns']:
                elements.append(Paragraph(f"• {pattern}", self.styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _create_fact_checks(self, results):
        """Create detailed fact checks section"""
        elements = []
        
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
            
            # Verdict
            elements.append(Paragraph(
                f"Verdict: {check['verdict'].replace('_', ' ').title()}",
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
    
    def _create_pattern_analysis(self, results):
        """Create pattern analysis section"""
        elements = []
        
        # Analyze patterns
        patterns = self._analyze_patterns(results['fact_checks'])
        
        if patterns:
            elements.append(PageBreak())
            elements.append(Paragraph("Pattern Analysis", self.styles['SectionHeader']))
            
            for pattern_type, details in patterns.items():
                elements.append(Paragraph(pattern_type, self.styles['Heading3']))
                elements.append(Paragraph(details, self.styles['Conversational']))
                elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _analyze_patterns(self, fact_checks):
        """Analyze patterns in fact checks"""
        patterns = {}
        
        # Count verdict types
        verdict_counts = {}
        topics = {}
        
        for check in fact_checks:
            verdict = check['verdict']
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
            
            # Extract topics (simplified - could be enhanced with NLP)
            claim_lower = check['claim'].lower()
            if any(word in claim_lower for word in ['economy', 'jobs', 'unemployment']):
                topics['economic'] = topics.get('economic', 0) + 1
            elif any(word in claim_lower for word in ['health', 'medical', 'covid']):
                topics['health'] = topics.get('health', 0) + 1
        
        # Misleading pattern
        if verdict_counts.get('misleading', 0) >= 3:
            patterns['Pattern of Misleading Statements'] = (
                f"We identified {verdict_counts['misleading']} misleading statements in this transcript. "
                f"This pattern suggests a tendency to present information in a way that, while not entirely "
                f"false, could lead listeners to incorrect conclusions. This is often more subtle than "
                f"outright falsehoods but can be equally problematic."
            )
        
        # Topic concentration
        if topics:
            max_topic = max(topics.items(), key=lambda x: x[1])
            if max_topic[1] >= 3:
                patterns[f'Concentration on {max_topic[0].title()} Claims'] = (
                    f"A significant number of claims ({max_topic[1]}) were related to {max_topic[0]} topics. "
                    f"When false or misleading claims cluster around specific topics, it may indicate either "
                    f"a lack of knowledge in that area or intentional misrepresentation."
                )
        
        return patterns
    
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
            ['Misleading', str(sum(1 for fc in results['fact_checks'] 
                                 if fc.get('verdict') == 'misleading'))],
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
