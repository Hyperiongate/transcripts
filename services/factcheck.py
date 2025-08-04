"""
Enhanced Fact Checking Service - Main Module
Coordinates fact-checking using multiple sources and enhanced verdicts
"""
import os
import time
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from config import Config
from .factcheck_history import FactCheckHistory
from .context_resolver import ContextResolver
from .verdict_definitions import VerdictDefinitions
from .api_checkers import APICheckers

logger = logging.getLogger(__name__)

class FactChecker:
    """Main fact-checking coordinator with enhanced features"""
    
    def __init__(self):
        # Initialize API keys
        api_keys = {
            'google': Config.GOOGLE_FACTCHECK_API_KEY,
            'fred': getattr(Config, 'FRED_API_KEY', None),
            'openai': getattr(Config, 'OPENAI_API_KEY', None),
            'mediastack': getattr(Config, 'MEDIASTACK_API_KEY', None),
            'news': getattr(Config, 'NEWS_API_KEY', None),
            'noaa': getattr(Config, 'NOAA_API_TOKEN', None),
            'crossref_email': getattr(Config, 'CROSSREF_EMAIL', 'factchecker@example.com')
        }
        
        # Initialize components
        self.history = FactCheckHistory()
        self.context_resolver = ContextResolver()
        self.verdict_defs = VerdictDefinitions()
        self.api_checkers = APICheckers(api_keys)
        
        # Validate setup
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate that the fact checker is properly configured"""
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            logger.warning("Google Fact Check API key not configured")
        
        active_apis = []
        if Config.GOOGLE_FACTCHECK_API_KEY:
            active_apis.append("Google Fact Check")
        if getattr(Config, 'FRED_API_KEY', None):
            active_apis.append("FRED")
        if getattr(Config, 'OPENAI_API_KEY', None):
            active_apis.append("OpenAI")
        
        logger.info(f"Fact checker initialized with APIs: {', '.join(active_apis)}")
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims with context awareness"""
        results = []
        
        for claim in claims:
            # Resolve context
            resolved_claim, context_info = self.context_resolver.resolve_context(claim)
            
            # Add to context history
            self.context_resolver.add_claim_to_context(claim)
            
            # Check the claim
            result = self.check_claim(resolved_claim)
            
            # Add context info if relevant
            if context_info.get('resolved'):
                result['context_resolution'] = context_info
            
            results.append(result)
            
            # Rate limiting
            time.sleep(Config.FACT_CHECK_RATE_LIMIT_DELAY)
        
        return results
    
    def check_claim(self, claim: str) -> Dict:
        """Check a single claim with all available sources"""
        # Check for vagueness
        vagueness_check = self.context_resolver.check_vagueness(claim)
        if vagueness_check['is_vague']:
            return self._create_unverified_response(
                claim, 
                f"Claim too vague: {vagueness_check['reason']}",
                vagueness_reason=vagueness_check['reason']
            )
        
        # Extract claim source
        claim_source = self.context_resolver.extract_claim_source(claim)
        
        # Check historical context
        historical_context = None
        if claim_source:
            historical_context = self.history.get_historical_context(claim, claim_source)
        
        # Run async checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._check_all_sources(claim))
            
            # Add historical context
            if historical_context:
                result = self._add_historical_context(result, historical_context)
            
            # Record in history
            if claim_source:
                self.history.add_check(claim, claim_source, result['verdict'], result['explanation'])
            
            return result
            
        finally:
            loop.close()
    
    async def _check_all_sources(self, claim: str) -> Dict:
        """Check claim with ALL available sources - no filtering"""
        tasks = []
        
        # Add all available API checks
        tasks.extend([
            self.api_checkers.check_google_factcheck(claim),
            self.api_checkers.analyze_with_openai(claim),
            self.api_checkers.check_fred_data(claim),
            self.api_checkers.check_wikipedia(claim),
            self.api_checkers.check_semantic_scholar(claim),
            self.api_checkers.check_cdc_data(claim),
            self.api_checkers.check_news_sources(claim)
        ])
        
        # Add more free API checks here as needed
        # tasks.extend([...])
        
        # Gather all results
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter valid results
        valid_results = []
        for result in all_results:
            if isinstance(result, dict) and result.get('found'):
                # Process OpenAI results specially
                if result.get('source') == 'OpenAI Analysis' and result.get('raw_analysis'):
                    result['verdict'] = self.verdict_defs.extract_verdict_from_text(result['raw_analysis'])
                # Map Google ratings
                elif result.get('source') == 'Google Fact Check':
                    result['verdict'] = self.verdict_defs.map_google_rating(result.get('verdict', ''))
                
                valid_results.append(result)
        
        if not valid_results:
            return self._create_unverified_response(claim, "No sources could verify this claim")
        
        # Synthesize results
        return self._synthesize_verdict(claim, valid_results)
    
    def _synthesize_verdict(self, claim: str, results: List[Dict]) -> Dict:
        """Synthesize final verdict from multiple sources"""
        verdicts = []
        explanations = []
        sources = []
        misleading_flags = []
        context_flags = []
        
        # Process each result
        for result in results:
            verdict = result.get('verdict', 'unverified')
            verdicts.append({
                'verdict': verdict,
                'confidence': result.get('confidence', 50),
                'weight': result.get('weight', 0.5),
                'source': result.get('source', 'Unknown')
            })
            
            explanation = result.get('explanation', '')
            explanations.append(f"{result['source']}: {explanation}")
            sources.append(result.get('source', 'Unknown'))
            
            # Check for special flags
            if 'misleading' in explanation.lower():
                misleading_flags.append(result['source'])
            if 'context' in explanation.lower() and 'lack' in explanation.lower():
                context_flags.append(result['source'])
        
        # Calculate consensus
        final_verdict = self._calculate_consensus(verdicts)
        
        # Adjust for special cases
        if misleading_flags and final_verdict in ['true', 'mostly_true']:
            final_verdict = 'misleading'
        elif context_flags and final_verdict in ['true', 'mostly_true']:
            final_verdict = 'lacks_context'
        
        # Calculate confidence
        confidence = self._calculate_confidence(verdicts)
        
        # Create explanation
        explanation = self._create_explanation(final_verdict, explanations, sources)
        
        # Categorize sources
        source_breakdown = self._categorize_sources(sources)
        
        return {
            'claim': claim,
            'verdict': final_verdict,
            'confidence': confidence,
            'explanation': explanation,
            'sources': list(set(sources)),
            'source_count': len(set(sources)),
            'source_breakdown': source_breakdown,
            'misleading_flags': misleading_flags,
            'context_flags': context_flags,
            'api_response': True
        }
    
    def _calculate_consensus(self, verdicts: List[Dict]) -> str:
        """Calculate consensus verdict"""
        if not verdicts:
            return 'unverified'
        
        verdict_scores = defaultdict(float)
        total_weight = 0
        
        for v in verdicts:
            verdict = v['verdict']
            weight = v['weight'] * (v['confidence'] / 100)
            verdict_scores[verdict] += weight
            total_weight += weight
        
        if total_weight == 0:
            return 'unverified'
        
        # Get highest scoring verdict
        best_verdict = max(verdict_scores.items(), key=lambda x: x[1])
        
        # Require strong consensus for definitive verdicts
        if best_verdict[0] in ['true', 'false'] and best_verdict[1] / total_weight < 0.7:
            return 'mixed'
        
        return best_verdict[0]
    
    def _calculate_confidence(self, verdicts: List[Dict]) -> int:
        """Calculate confidence score"""
        if not verdicts:
            return 0
        
        # Base confidence on source count
        base = min(len(verdicts) * 15, 60)
        
        # Agreement bonus
        unique_verdicts = len(set(v['verdict'] for v in verdicts))
        if unique_verdicts == 1:
            agreement_bonus = 30
        elif unique_verdicts == 2:
            agreement_bonus = 15
        else:
            agreement_bonus = 0
        
        # High-weight source bonus
        weight_bonus = sum(min(v['weight'] * 10, 10) for v in verdicts if v['weight'] > 0.7)
        
        return min(int(base + agreement_bonus + weight_bonus), 95)
    
    def _create_explanation(self, verdict: str, explanations: List[str], sources: List[str]) -> str:
        """Create detailed explanation"""
        verdict_info = self.verdict_defs.get_verdict_info(verdict)
        
        prefix = f"{verdict_info['icon']} {verdict_info['label'].upper()}: "
        description = verdict_info['description']
        
        # Add source count
        source_count = len(set(sources))
        source_summary = f" (Checked by {source_count} source{'s' if source_count != 1 else ''})"
        
        # Find most relevant explanation
        if explanations:
            # Prefer explanations with numbers/data
            data_explanations = [e for e in explanations if any(c.isdigit() for c in e)]
            key_explanation = data_explanations[0] if data_explanations else explanations[0]
            
            return f"{prefix}{description}. {key_explanation}{source_summary}"
        
        return f"{prefix}{description}{source_summary}"
    
    def _categorize_sources(self, sources: List[str]) -> Dict[str, int]:
        """Categorize sources by type"""
        categories = defaultdict(int)
        
        for source in sources:
            source_lower = source.lower()
            
            if 'fact check' in source_lower:
                categories['Fact Checkers'] += 1
            elif any(term in source_lower for term in ['fred', 'economic', 'federal reserve']):
                categories['Economic Data'] += 1
            elif any(term in source_lower for term in ['news', 'media']):
                categories['News Media'] += 1
            elif any(term in source_lower for term in ['academic', 'scholar', 'research']):
                categories['Academic Sources'] += 1
            elif 'ai' in source_lower or 'openai' in source_lower:
                categories['AI Analysis'] += 1
            elif any(term in source_lower for term in ['cdc', 'health', 'medical']):
                categories['Health/Medical'] += 1
            else:
                categories['Other Sources'] += 1
        
        return dict(categories)
    
    def _add_historical_context(self, result: Dict, historical_context: Dict) -> Dict:
        """Add historical context to result"""
        if historical_context.get('previously_checked'):
            count = historical_context['check_count']
            result['explanation'] += f" NOTE: This claim has been checked {count} time{'s' if count != 1 else ''} before."
        
        elif historical_context.get('source_history'):
            stats = historical_context['source_history']
            if stats['false_claims'] > 2:
                result['explanation'] += f" PATTERN: This source has made {stats['false_claims']} false claims previously."
        
        return result
    
    def _create_unverified_response(self, claim: str, reason: str, **kwargs) -> Dict:
        """Create response for unverified claims"""
        response = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': f"? UNVERIFIED: {reason}",
            'sources': [],
            'api_response': False
        }
        
        response.update(kwargs)
        return response
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> int:
        """Calculate overall credibility score from fact check results"""
        if not fact_checks:
            return 50
        
        verdicts = []
        for fc in fact_checks:
            verdict = fc.get('verdict', 'unverified')
            # Normalize verdict format (handle both underscore and space)
            verdict = verdict.lower().replace(' ', '_')
            verdicts.append(verdict)
        
        # Use the centralized credibility calculation
        return self.verdict_defs.calculate_credibility_score(verdicts)
    
    async def check_speaker_background(self, speaker_name: str) -> Dict:
        """Check speaker's background and credibility history"""
        if not speaker_name or speaker_name in ['INTERVIEWER', 'INTERVIEWEE', 'Unknown']:
            return {}
        
        background_info = {
            'name': speaker_name,
            'credibility_issues': [],
            'criminal_record': None,
            'lawsuits': [],
            'fact_check_history': {},
            'controversies': []
        }
        
        # Search for fact-check history
        if self.api_checkers.google_api_key:
            try:
                # Search for past fact checks of this person
                search_query = f'"{speaker_name}" fact check false misleading'
                results = await self.api_checkers.check_google_factcheck(search_query)
                
                if results.get('found'):
                    background_info['fact_check_history']['has_false_claims'] = True
                    background_info['fact_check_history']['details'] = results.get('explanation', '')
                    background_info['credibility_issues'].append('Previously made false claims')
            except:
                pass
        
        # Search news for controversies, lawsuits, criminal records
        controversy_keywords = [
            'lawsuit', 'sued', 'criminal', 'convicted', 'arrested', 'indicted',
            'scandal', 'controversy', 'investigation', 'fraud', 'corruption',
            'lying', 'false claims', 'misleading', 'deception'
        ]
        
        for keyword in controversy_keywords[:5]:  # Limit searches
            search_query = f'"{speaker_name}" {keyword}'
            news_results = await self.api_checkers.check_news_sources(search_query)
            
            if news_results.get('found'):
                if keyword in ['lawsuit', 'sued']:
                    background_info['lawsuits'].append({
                        'keyword': keyword,
                        'found': True,
                        'details': news_results.get('explanation', '')
                    })
                elif keyword in ['criminal', 'convicted', 'arrested', 'indicted']:
                    if not background_info['criminal_record']:
                        background_info['criminal_record'] = {
                            'found': True,
                            'details': news_results.get('explanation', '')
                        }
                else:
                    background_info['controversies'].append({
                        'type': keyword,
                        'details': news_results.get('explanation', '')
                    })
        
        # Check Wikipedia for general background
        wiki_results = await self.api_checkers.check_wikipedia(speaker_name)
        if wiki_results.get('found'):
            background_info['wikipedia_entry'] = True
            background_info['is_public_figure'] = True
        
        # Compile credibility assessment
        if background_info['fact_check_history'].get('has_false_claims'):
            background_info['credibility_assessment'] = 'History of false or misleading claims'
            background_info['credibility_score'] = 'Low'
        elif background_info['criminal_record']:
            background_info['credibility_assessment'] = 'Criminal record found - evaluate claims carefully'
            background_info['credibility_score'] = 'Questionable'
        elif len(background_info['lawsuits']) > 2:
            background_info['credibility_assessment'] = 'Multiple lawsuits found - potential credibility concerns'
            background_info['credibility_score'] = 'Mixed'
        elif background_info['controversies']:
            background_info['credibility_assessment'] = 'Some controversies found - standard verification recommended'
            background_info['credibility_score'] = 'Moderate'
        else:
            background_info['credibility_assessment'] = 'No major credibility issues found'
            background_info['credibility_score'] = 'Standard'
        
        return background_info
    
    def generate_executive_summary(self, results: Dict) -> str:
        """Generate an executive summary of the fact-check analysis"""
        summary_parts = []
        
        # Overall assessment
        score = results.get('credibility_score', 0)
        label = results.get('credibility_label', 'Unknown')
        total_claims = results.get('checked_claims', 0)
        
        if score >= 80:
            assessment = "The transcript demonstrates high credibility with most claims verified as accurate."
        elif score >= 60:
            assessment = "The transcript shows moderate credibility with a mix of accurate and questionable claims."
        elif score >= 40:
            assessment = "The transcript exhibits low credibility with numerous false or unverifiable claims."
        else:
            assessment = "The transcript shows very low credibility with predominantly false or misleading claims."
        
        summary_parts.append(assessment)
        
        # Key findings
        fact_checks = results.get('fact_checks', [])
        false_claims = [fc for fc in fact_checks if fc.get('verdict') in ['false', 'mostly_false']]
        misleading_claims = [fc for fc in fact_checks if fc.get('verdict') in ['misleading', 'lacks_context']]
        
        if false_claims:
            summary_parts.append(f"\n\nKey False Claims Identified ({len(false_claims)}):")
            for fc in false_claims[:3]:  # Top 3 false claims
                summary_parts.append(f"• \"{fc['claim'][:100]}...\" - {fc.get('explanation', 'No explanation available')}")
        
        if misleading_claims:
            summary_parts.append(f"\n\nMisleading or Context-Lacking Claims ({len(misleading_claims)}):")
            for fc in misleading_claims[:2]:
                summary_parts.append(f"• \"{fc['claim'][:100]}...\" - Missing important context")
        
        # Speaker credibility (if available)
        if results.get('speaker_analysis'):
            speaker_info = results['speaker_analysis']
            if speaker_info.get('credibility_score') in ['Low', 'Questionable']:
                summary_parts.append(f"\n\n⚠️ Speaker Credibility Warning: {speaker_info.get('credibility_assessment', 'Issues found with speaker credibility')}")
        
        # Recommendations
        summary_parts.append("\n\nRecommendations:")
        if score < 60:
            summary_parts.append("• Verify all claims independently before accepting as fact")
            summary_parts.append("• Cross-reference with multiple reliable sources")
            summary_parts.append("• Be aware of potential bias or misinformation")
        else:
            summary_parts.append("• Most claims appear accurate but always verify critical information")
            summary_parts.append("• Pay attention to claims flagged as lacking context")
        
        return '\n'.join(summary_parts)
    
    def get_historical_summary(self) -> Dict:
        """Get summary of historical fact-checking patterns"""
        repeat_offenders = self.history.get_repeat_offenders()
        
        return {
            'total_claims_checked': len(self.history.claim_history),
            'unique_sources': len(self.history.source_patterns),
            'repeat_offenders': repeat_offenders
        }
