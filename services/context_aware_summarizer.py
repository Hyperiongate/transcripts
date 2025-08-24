"""
Context-Aware Summarizer Service
Generates intelligent summaries of fact-checking results
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ContextAwareSummarizer:
    """Generate context-aware summaries of fact-checking results"""
    
    def __init__(self):
        self.verdict_labels = {
            'verified_true': 'Verified as True',
            'verified_false': 'Verified as False',
            'partially_accurate': 'Partially Accurate',
            'unverifiable': 'Unverifiable',
            'opinion': 'Opinion/Subjective',
            'misleading': 'Misleading',
            'needs_context': 'Needs Context'
        }
    
    def generate_summary(self, results: Dict) -> str:
        """Generate a comprehensive summary of fact-checking results"""
        try:
            # Extract key data
            cred_score = results.get('credibility_score', {})
            score = cred_score.get('score', 0)
            label = cred_score.get('label', 'Unknown')
            verdict_counts = cred_score.get('verdict_counts', {})
            total_claims = results.get('total_claims', 0)
            fact_checks = results.get('fact_checks', [])
            
            # Build summary parts
            summary_parts = []
            
            # Opening statement with score
            summary_parts.append(self._generate_opening_statement(score, label, total_claims))
            
            # Verdict breakdown
            if verdict_counts:
                summary_parts.append(self._generate_verdict_breakdown(verdict_counts, total_claims))
            
            # Key findings
            key_findings = self._extract_key_findings(fact_checks)
            if key_findings:
                summary_parts.append(self._generate_key_findings_section(key_findings))
            
            # Pattern analysis
            patterns = self._analyze_patterns(fact_checks)
            if patterns:
                summary_parts.append(self._generate_pattern_section(patterns))
            
            # Conclusion
            summary_parts.append(self._generate_conclusion(score, label, verdict_counts))
            
            return "\n\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return self._generate_fallback_summary(results)
    
    def _generate_opening_statement(self, score: int, label: str, total_claims: int) -> str:
        """Generate opening statement"""
        if total_claims == 0:
            return "No verifiable claims were found in this transcript."
        
        if score >= 85:
            tone = "demonstrates high credibility with"
        elif score >= 70:
            tone = "shows generally good credibility with"
        elif score >= 50:
            tone = "has mixed credibility with"
        else:
            tone = "shows concerning credibility issues with"
        
        return f"This transcript {tone} a credibility score of {score}/100. Analysis of {total_claims} claims reveals: {label}."
    
    def _generate_verdict_breakdown(self, verdict_counts: Dict, total_claims: int) -> str:
        """Generate verdict breakdown section"""
        if not verdict_counts:
            return ""
        
        breakdown = []
        
        # Sort by count descending
        sorted_verdicts = sorted(verdict_counts.items(), key=lambda x: x[1], reverse=True)
        
        for verdict, count in sorted_verdicts:
            if count > 0:
                percentage = (count / total_claims * 100) if total_claims > 0 else 0
                label = self.verdict_labels.get(verdict, verdict.replace('_', ' ').title())
                breakdown.append(f"• {label}: {count} claims ({percentage:.1f}%)")
        
        return "Breakdown of claims:\n" + "\n".join(breakdown)
    
    def _extract_key_findings(self, fact_checks: List[Dict]) -> List[Dict]:
        """Extract the most important findings"""
        key_findings = []
        
        # Get verified false claims (highest priority)
        false_claims = [fc for fc in fact_checks if fc.get('verdict') == 'verified_false']
        for claim in false_claims[:3]:  # Top 3 false claims
            key_findings.append({
                'type': 'false',
                'claim': claim.get('claim', ''),
                'explanation': claim.get('explanation', ''),
                'speaker': claim.get('speaker', 'Unknown')
            })
        
        # Get highly confident true claims
        true_claims = [fc for fc in fact_checks 
                      if fc.get('verdict') == 'verified_true' 
                      and fc.get('confidence', 0) >= 90]
        for claim in true_claims[:2]:  # Top 2 true claims
            key_findings.append({
                'type': 'true',
                'claim': claim.get('claim', ''),
                'explanation': claim.get('explanation', ''),
                'speaker': claim.get('speaker', 'Unknown')
            })
        
        return key_findings
    
    def _generate_key_findings_section(self, key_findings: List[Dict]) -> str:
        """Generate key findings section"""
        if not key_findings:
            return ""
        
        sections = []
        
        # False claims
        false_findings = [f for f in key_findings if f['type'] == 'false']
        if false_findings:
            sections.append("❌ Key False Claims:")
            for finding in false_findings:
                speaker = finding['speaker']
                claim = finding['claim'][:100] + "..." if len(finding['claim']) > 100 else finding['claim']
                sections.append(f"  • {speaker}: \"{claim}\"")
                if finding['explanation']:
                    sections.append(f"    → {finding['explanation']}")
        
        # True claims
        true_findings = [f for f in key_findings if f['type'] == 'true']
        if true_findings:
            if sections:  # Add spacing if we have false claims
                sections.append("")
            sections.append("✓ Verified True Claims:")
            for finding in true_findings:
                speaker = finding['speaker']
                claim = finding['claim'][:100] + "..." if len(finding['claim']) > 100 else finding['claim']
                sections.append(f"  • {speaker}: \"{claim}\"")
        
        return "\n".join(sections)
    
    def _analyze_patterns(self, fact_checks: List[Dict]) -> Dict:
        """Analyze patterns in the fact checks"""
        patterns = {
            'speakers_with_false_claims': {},
            'topics_with_issues': {},
            'high_confidence_false': 0,
            'low_confidence_true': 0
        }
        
        for fc in fact_checks:
            verdict = fc.get('verdict', '')
            speaker = fc.get('speaker', 'Unknown')
            confidence = fc.get('confidence', 50)
            
            # Track speakers with false claims
            if verdict == 'verified_false':
                if speaker not in patterns['speakers_with_false_claims']:
                    patterns['speakers_with_false_claims'][speaker] = 0
                patterns['speakers_with_false_claims'][speaker] += 1
                
                if confidence >= 80:
                    patterns['high_confidence_false'] += 1
            
            # Track low confidence true claims
            elif verdict == 'verified_true' and confidence < 60:
                patterns['low_confidence_true'] += 1
        
        return patterns
    
    def _generate_pattern_section(self, patterns: Dict) -> str:
        """Generate pattern analysis section"""
        sections = []
        
        # Speakers with multiple false claims
        if patterns['speakers_with_false_claims']:
            speakers = sorted(patterns['speakers_with_false_claims'].items(), 
                            key=lambda x: x[1], reverse=True)
            if speakers[0][1] >= 2:  # At least 2 false claims
                sections.append("⚠️ Pattern Alert:")
                for speaker, count in speakers:
                    if count >= 2:
                        sections.append(f"  • {speaker} made {count} false claims")
        
        # High confidence false claims
        if patterns['high_confidence_false'] >= 2:
            sections.append(f"  • {patterns['high_confidence_false']} demonstrably false claims with high confidence")
        
        return "\n".join(sections) if sections else ""
    
    def _generate_conclusion(self, score: int, label: str, verdict_counts: Dict) -> str:
        """Generate conclusion section"""
        verified_false = verdict_counts.get('verified_false', 0)
        verified_true = verdict_counts.get('verified_true', 0)
        unverifiable = verdict_counts.get('unverifiable', 0)
        
        if score >= 85 and verified_false == 0:
            return "💚 Overall Assessment: This transcript demonstrates high credibility with claims that are largely accurate and verifiable."
        elif score >= 70:
            return "🟡 Overall Assessment: This transcript shows generally reliable information with some minor inaccuracies that should be noted."
        elif verified_false > verified_true:
            return "🔴 Overall Assessment: This transcript contains multiple false or misleading claims that significantly impact its credibility."
        elif unverifiable > (verified_true + verified_false):
            return "⚪ Overall Assessment: Many claims in this transcript could not be independently verified. Additional sources may be needed."
        else:
            return "🟡 Overall Assessment: This transcript contains a mix of accurate and inaccurate information. Readers should verify key claims independently."
    
    def _generate_fallback_summary(self, results: Dict) -> str:
        """Generate a basic summary if detailed analysis fails"""
        total_claims = results.get('total_claims', 0)
        cred_score = results.get('credibility_score', {})
        score = cred_score.get('score', 0)
        
        return f"""This transcript was analyzed for factual accuracy. 
        
Total claims checked: {total_claims}
Credibility score: {score}/100

The analysis examined various claims made in the transcript and verified them against available sources. 
Please review individual claim results for detailed information."""
    
    def generate_enhanced_summary(self, results: Dict) -> str:
        """Enhanced summary generation with more context"""
        # This is an alias for the main generate_summary method
        # but could be extended with additional features
        return self.generate_summary(results)
    
    def generate_speaker_summary(self, speaker_name: str, speaker_facts: List[Dict]) -> str:
        """Generate summary for a specific speaker"""
        if not speaker_facts:
            return f"No claims analyzed for {speaker_name}."
        
        verdict_counts = {}
        for fc in speaker_facts:
            verdict = fc.get('verdict', 'unknown')
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        total = len(speaker_facts)
        false_claims = verdict_counts.get('verified_false', 0)
        true_claims = verdict_counts.get('verified_true', 0)
        
        if false_claims > true_claims:
            assessment = "made multiple false claims"
        elif true_claims > false_claims:
            assessment = "made mostly accurate statements"
        else:
            assessment = "made mixed statements"
        
        return f"{speaker_name} {assessment} ({true_claims} true, {false_claims} false out of {total} claims checked)."
