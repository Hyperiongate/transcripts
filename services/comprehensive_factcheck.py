from collections import defaultdict
"""
Comprehensive Fact-Checking Service that uses ALL available APIs
"""
import re
import logging
import requests
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

# Import all our services
from .api_checkers import APICheckers
from .context_resolver import ContextResolver
from .factcheck_history import FactCheckHistory

logger = logging.getLogger(__name__)

# Keep the verdict categories from original
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

class ComprehensiveFactChecker:
    """Enhanced fact-checking that actually uses all available services"""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize all API keys (excluding scraper)
        self.api_keys = {
            'google': getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None),
            'openai': getattr(config, 'OPENAI_API_KEY', None),
            'fred': getattr(config, 'FRED_API_KEY', None),
            'news': getattr(config, 'NEWS_API_KEY', None),
            'mediastack': getattr(config, 'MEDIASTACK_API_KEY', None),
            'noaa': getattr(config, 'NOAA_TOKEN', None),
            'census': getattr(config, 'CENSUS_API_KEY', None),
            'cdc': getattr(config, 'CDC_API_KEY', None),
        }
        
        # Initialize services
        self.api_checkers = APICheckers(self.api_keys)
        self.context_resolver = ContextResolver()
        self.fact_history = FactCheckHistory()
        
        # Initialize OpenAI if available
        self.openai_client = None
        if self.api_keys['openai']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.api_keys['openai'])
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Thread pool for parallel API calls
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Main entry point - check claim using ALL available resources"""
        try:
            # Clean claim
            claim = claim.strip()
            
            # Check if this is trivial content
            if self._is_trivial_claim(claim):
                return None  # Skip trivial claims entirely
            
            # Check if too short but not trivial
            if len(claim.split()) < 4:
                return self._create_verdict('needs_context', 'Statement too short to analyze meaningfully')
            
            # Resolve context (pronouns, references)
            if context and context.get('transcript'):
                self.context_resolver.analyze_full_transcript(context['transcript'])
            
            resolved_claim, context_info = self.context_resolver.resolve_context(claim)
            if resolved_claim != claim:
                logger.info(f"Resolved claim: {claim} -> {resolved_claim}")
                claim = resolved_claim
            
            # Check if claim is too vague
            vagueness = self.context_resolver.is_claim_too_vague(claim)
            if vagueness['is_vague'] and not self._contains_implicit_facts(claim):
                return self._create_verdict('needs_context', vagueness['reason'])
            
            # Check historical patterns
            speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            historical = self.fact_history.get_historical_context(claim, speaker)
            
            # Even if it's an opinion, analyze it for factual components
            is_opinion = self._is_opinion_with_facts(claim)
            
            # Run comprehensive fact-checking
            result = asyncio.run(self._comprehensive_check(claim, speaker, historical, is_opinion))
            
            # Add to history
            self.fact_history.add_check(claim, speaker, result['verdict'], result['explanation'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fact-check: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    def _is_trivial_claim(self, claim: str) -> bool:
        """Check if claim is trivial and should be skipped"""
        trivial_patterns = [
            r'^(hi|hello|hey|good\s+(morning|afternoon|evening|night))',
            r'^(thank\s+you|thanks)',
            r'^(welcome|you\'re welcome)',
            r'^(please|excuse me)',
            r'^(um+|uh+|ah+|oh+|hmm+)',
            r'^(yes|no|yeah|nope|yep|okay|ok|alright)',
            r'^(i mean|you know|like|so|well|anyway)',
            r'^\s*\[.*?\]\s*$',  # Stage directions
            r'^(applause|laughter|music)',
        ]
        
        claim_lower = claim.lower().strip()
        for pattern in trivial_patterns:
            if re.match(pattern, claim_lower):
                return True
        
        # Also skip if under 10 characters or 3 words
        if len(claim) < 10 or len(claim.split()) < 3:
            return True
            
        return False
    
    def _is_opinion_with_facts(self, claim: str) -> bool:
        """Check if claim is opinion but contains factual elements to analyze"""
        opinion_indicators = [
            'cannot manage', 'stumbling into', 'catastrophic',
            'terrible', 'great', 'amazing', 'horrible', 'disaster',
            'best', 'worst', 'failure', 'success'
        ]
        
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in opinion_indicators)
    
    def _contains_implicit_facts(self, claim: str) -> bool:
        """Check if claim contains implicit factual assertions"""
        factual_indicators = [
            'government', 'crisis', 'policy', 'economy', 'border',
            'war', 'conflict', 'spending', 'deficit', 'crime',
            'immigration', 'healthcare', 'education'
        ]
        
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in factual_indicators)
    
    async def _comprehensive_check(self, claim: str, speaker: str, historical: Optional[Dict], is_opinion: bool) -> Dict:
        """Run all fact-checking methods in parallel"""
        
        # If it's an opinion, first extract factual components
        if is_opinion:
            factual_components = await self._extract_factual_components(claim)
            if factual_components:
                return await self._analyze_opinion_with_facts(claim, factual_components, speaker, historical)
        
        # Otherwise, proceed with normal fact-checking
        tasks = []
        
        # 1. Google Fact Check
        if self.api_keys['google']:
            tasks.append(('google', self.api_checkers.check_google_factcheck(claim)))
        
        # 2. AI Analysis - Enhanced for opinions
        if self.openai_client:
            tasks.append(('ai', self._check_with_ai_comprehensive(claim, is_opinion)))
        
        # 3. Economic data (FRED)
        if self._is_economic_claim(claim) and self.api_keys['fred']:
            tasks.append(('fred', self.api_checkers.check_fred_data(claim)))
        
        # 4. News sources
        if self.api_keys['news'] or self.api_keys['mediastack']:
            tasks.append(('news', self.api_checkers.check_news_sources(claim)))
        
        # 5. Wikipedia
        tasks.append(('wikipedia', self.api_checkers.check_wikipedia(claim)))
        
        # 6. Government data sources
        if self._is_government_data_claim(claim):
            if 'health' in claim.lower() or 'covid' in claim.lower():
                tasks.append(('cdc', self.api_checkers.check_cdc_data(claim)))
            if 'population' in claim.lower() or 'demographic' in claim.lower():
                tasks.append(('census', self.api_checkers.check_census_data(claim)))
            if 'climate' in claim.lower() or 'weather' in claim.lower():
                tasks.append(('noaa', self.api_checkers.check_noaa_data(claim)))
        
        # 7. Academic sources
        if self._is_academic_claim(claim):
            tasks.append(('academic', self.api_checkers.check_semantic_scholar(claim)))
        
        # Execute all tasks in parallel
        results = {}
        if tasks:
            task_names = [t[0] for t in tasks]
            task_coroutines = [t[1] for t in tasks]
            
            completed = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            for name, result in zip(task_names, completed):
                if isinstance(result, Exception):
                    logger.error(f"{name} check failed: {result}")
                    results[name] = {'found': False}
                else:
                    results[name] = result
        
        # Aggregate results
        return self._aggregate_results(claim, results, speaker, historical)
    
    async def _extract_factual_components(self, claim: str) -> List[Dict]:
        """Extract factual components from an opinion statement"""
        if not self.openai_client:
            return []
        
        try:
            prompt = f"""Analyze this statement and extract any factual claims or assumptions that can be verified:

Statement: "{claim}"

Identify:
1. What specific events, policies, or situations might this refer to?
2. What factual claims are implicit in this statement?
3. What data or evidence would be needed to evaluate this fairly?

Format your response as a list of specific, verifiable claims."""

            response = self.openai_client.chat.completions.create(
                model='gpt-4' if hasattr(self.config, 'USE_GPT4') and self.config.USE_GPT4 else 'gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "Extract factual components from opinions for verification."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Parse the response to extract factual claims
            content = response.choices[0].message.content
            factual_claims = []
            
            # Simple parsing - could be enhanced
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('Identify:', 'Format:', '1.', '2.', '3.')):
                    if len(line) > 20:  # Skip very short lines
                        factual_claims.append({
                            'claim': line.strip('- •'),
                            'original': claim
                        })
            
            return factual_claims[:5]  # Limit to 5 most relevant
            
        except Exception as e:
            logger.error(f"Error extracting factual components: {e}")
            return []
    
    async def _analyze_opinion_with_facts(self, original_claim: str, factual_components: List[Dict], 
                                         speaker: str, historical: Optional[Dict]) -> Dict:
        """Analyze an opinion by checking its factual components"""
        
        # Check each factual component
        component_results = []
        for component in factual_components:
            result = await self._comprehensive_check(component['claim'], speaker, historical, False)
            component_results.append({
                'claim': component['claim'],
                'result': result
            })
        
        # Build comprehensive explanation
        explanation_parts = [
            f"This is an opinion statement that contains several factual implications. Here's what we found:\n"
        ]
        
        # Add analysis of each component
        for i, comp_result in enumerate(component_results, 1):
            verdict = comp_result['result']['verdict']
            exp = comp_result['result']['explanation']
            explanation_parts.append(f"\n{i}. Regarding '{comp_result['claim']}':")
            explanation_parts.append(f"   Verdict: {verdict}")
            explanation_parts.append(f"   {exp}")
        
        # Add context and balance
        explanation_parts.append("\n\nCONTEXT AND BALANCE:")
        explanation_parts.append(self._get_balanced_context(original_claim))
        
        # Determine overall verdict based on factual components
        verdicts = [cr['result']['verdict'] for cr in component_results]
        if all(v in ['true', 'mostly_true'] for v in verdicts):
            final_verdict = 'opinion'
            explanation_parts.append("\n\nThe factual premises underlying this opinion are largely supported by evidence.")
        elif all(v in ['false', 'mostly_false'] for v in verdicts):
            final_verdict = 'misleading'
            explanation_parts.append("\n\nThe factual premises underlying this opinion are not supported by evidence.")
        else:
            final_verdict = 'opinion'
            explanation_parts.append("\n\nThe factual premises underlying this opinion are mixed - some supported, others not.")
        
        return self._create_verdict(
            final_verdict,
            '\n'.join(explanation_parts),
            confidence=75,
            sources=['Multiple sources analyzed']
        )
    
    def _get_balanced_context(self, claim: str) -> str:
        """Get balanced context for controversial claims"""
        claim_lower = claim.lower()
        
        if 'government' in claim_lower and 'crisis' in claim_lower:
            return """
- Supporting view: Some point to challenges like border management, inflation, or supply chain issues as evidence of management difficulties.
- Opposing view: Others cite job growth, infrastructure investments, and diplomatic achievements as signs of effective governance.
- Historical context: Every administration faces crises; assessments often depend on political perspective and which metrics are prioritized."""
        
        elif 'catastrophic' in claim_lower and 'abroad' in claim_lower:
            return """
- Supporting view: Critics point to situations in Afghanistan, Ukraine tensions, or Middle East conflicts as foreign policy challenges.
- Opposing view: Supporters highlight strengthened alliances, diplomatic engagements, and avoided conflicts as successes.
- Context: Foreign policy assessments vary widely based on ideological perspective and which global issues are emphasized."""
        
        else:
            return """
- Note: Political assessments are inherently subjective and depend heavily on which metrics and events are prioritized.
- Different sources and perspectives will evaluate the same events very differently.
- Readers should consider multiple viewpoints and primary sources when forming their own conclusions."""
    
    async def _check_with_ai_comprehensive(self, claim: str, is_opinion: bool = False) -> Dict:
        """Use AI for comprehensive fact-checking"""
        try:
            if is_opinion:
                prompt = f"""Analyze this opinion statement for factual accuracy:
Statement: "{claim}"

1. What specific events or policies might this refer to?
2. What evidence supports this view?
3. What evidence contradicts this view?
4. What context is important for understanding this fairly?

Provide a balanced analysis with specific examples."""
            else:
                prompt = f"""Fact-check this claim comprehensively:
Claim: "{claim}"

Analyze:
1. Is this claim verifiable?
2. What are the key facts to check?
3. Is the claim true, false, or partially true?
4. What context is important?

Provide a clear verdict (TRUE/FALSE/MIXED/CANNOT_VERIFY) and explanation.
Focus on factual accuracy only."""

            response = self.openai_client.chat.completions.create(
                model='gpt-4' if hasattr(self.config, 'USE_GPT4') and self.config.USE_GPT4 else 'gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a fact-checker. Be objective, thorough, and provide balanced analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            
            # Parse response
            verdict = 'needs_context'
            if not is_opinion:
                if 'TRUE' in result.upper():
                    verdict = 'true'
                elif 'FALSE' in result.upper():
                    verdict = 'false'
                elif 'MIXED' in result.upper() or 'PARTIALLY' in result.upper():
                    verdict = 'mixed'
            else:
                verdict = 'opinion'
            
            # Extract explanation - use the full response for opinions
            explanation = result if is_opinion else self._extract_explanation(result)
            confidence = self._extract_confidence(result)
            
            return {
                'found': True,
                'verdict': verdict,
                'explanation': explanation,
                'confidence': confidence,
                'source': 'AI Analysis',
                'weight': 0.7
            }
            
        except Exception as e:
            logger.error(f"AI comprehensive check error: {e}")
            return {'found': False}
    
    def _aggregate_results(self, claim: str, results: Dict, speaker: str, historical: Optional[Dict]) -> Dict:
        """Aggregate results from multiple sources into final verdict"""
        
        # Track findings
        verdicts = []
        explanations = []
        sources_used = []
        total_confidence = 0
        
        # Process each result
        for source, result in results.items():
            if result.get('found'):
                verdict = result.get('verdict')
                if verdict and verdict != 'needs_context':
                    weight = result.get('weight', 0.5)
                    confidence = result.get('confidence', 50)
                    
                    verdicts.append({
                        'verdict': verdict,
                        'weight': weight,
                        'confidence': confidence,
                        'source': source
                    })
                    
                    if result.get('explanation'):
                        explanations.append(f"{source.upper()}: {result['explanation']}")
                    
                    sources_used.append(result.get('source', source))
        
        # If no results found, try pattern matching
        if not verdicts:
            pattern_result = self._check_common_patterns(claim)
            if pattern_result:
                return pattern_result
            
            # For claims with implicit facts, provide analysis anyway
            if self._contains_implicit_facts(claim):
                return self._create_verdict(
                    'opinion',
                    'This appears to be an opinion containing factual implications. Without access to specific data sources, we cannot verify the underlying claims. Readers should seek primary sources and consider multiple perspectives.',
                    confidence=30
                )
            
            return self._create_verdict(
                'needs_context',
                'Unable to verify through available sources. Consider checking primary sources directly.',
                confidence=30
            )
        
        # Calculate weighted verdict
        verdict_scores = {
            'true': 1.0,
            'mostly_true': 0.8,
            'nearly_true': 0.7,
            'mixed': 0.5,
            'misleading': 0.3,
            'mostly_false': 0.2,
            'false': 0.0
        }
        
        weighted_score = 0
        total_weight = 0
        verdict_count = defaultdict(int)
        
        for v in verdicts:
            verdict_type = self._normalize_verdict(v['verdict'])
            weight = v['weight']
            verdict_count[verdict_type] += 1
            
            if verdict_type in verdict_scores:
                weighted_score += verdict_scores[verdict_type] * weight
                total_weight += weight
                total_confidence += v['confidence'] * weight
        
        # Determine final verdict
        if total_weight > 0:
            final_score = weighted_score / total_weight
            avg_confidence = int(total_confidence / total_weight)
            
            if final_score >= 0.85:
                final_verdict = 'true'
            elif final_score >= 0.70:
                final_verdict = 'mostly_true'
            elif final_score >= 0.60:
                final_verdict = 'nearly_true'
            elif final_score >= 0.40:
                final_verdict = 'misleading'
            elif final_score >= 0.20:
                final_verdict = 'mostly_false'
            else:
                final_verdict = 'false'
        else:
            final_verdict = 'needs_context'
            avg_confidence = 30
        
        # Build comprehensive explanation
        explanation_parts = []
        
        # Add source-specific findings
        if explanations:
            explanation_parts.append("FINDINGS FROM MULTIPLE SOURCES:")
            explanation_parts.extend(explanations)
        
        # Add balanced context for controversial topics
        if self._is_controversial_topic(claim):
            explanation_parts.append("\nADDITIONAL CONTEXT:")
            explanation_parts.append(self._get_balanced_context(claim))
        
        # Add historical context
        if historical and historical.get('pattern'):
            explanation_parts.append(f"\nSPEAKER HISTORY: {speaker} has a pattern of {historical['pattern']}.")
        
        # Join all parts
        explanation = '\n'.join(explanation_parts) if explanation_parts else 'Based on available evidence.'
        
        return self._create_verdict(
            final_verdict,
            explanation,
            confidence=avg_confidence,
            sources=sources_used
        )
    
    def _is_controversial_topic(self, claim: str) -> bool:
        """Check if claim involves controversial topics needing balanced context"""
        controversial_keywords = [
            'government', 'administration', 'president', 'congress',
            'democrat', 'republican', 'liberal', 'conservative',
            'immigration', 'abortion', 'gun', 'climate', 'vaccine',
            'election', 'voter', 'fraud', 'crisis', 'border'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in controversial_keywords)
    
    def _extract_explanation(self, text: str, default: str = "See analysis") -> str:
        """Extract explanation from text"""
        # For comprehensive responses, return more of the content
        if len(text) > 200:
            return text  # Return full analysis for detailed responses
        
        # Try to find explanation section
        pattern = r'(?:Explanation|Analysis|Reasoning|Evidence):\s*(.+?)(?=\n[A-Z]+:|$)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else default
    
    def _extract_confidence(self, text: str) -> int:
        """Extract confidence from text"""
        # Look for confidence mentions
        pattern = r'(?:confidence|certainty):\s*(\d+)%?'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Default based on language
        if any(word in text.lower() for word in ['definitely', 'certainly', 'clearly']):
            return 90
        elif any(word in text.lower() for word in ['likely', 'probably', 'appears']):
            return 70
        elif any(word in text.lower() for word in ['possibly', 'might', 'could']):
            return 50
        else:
            return 60
    
    def _is_economic_claim(self, claim: str) -> bool:
        """Check if claim is about economic data"""
        economic_keywords = [
            'unemployment', 'inflation', 'gdp', 'economy', 'jobs',
            'wage', 'income', 'deficit', 'debt', 'budget', 'trade',
            'tariff', 'tax', 'revenue', 'spending', 'growth'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in economic_keywords)
    
    def _is_government_data_claim(self, claim: str) -> bool:
        """Check if claim relates to government data"""
        gov_keywords = [
            'census', 'population', 'demographic', 'health', 'covid',
            'disease', 'climate', 'temperature', 'weather', 'storm',
            'immigration', 'crime', 'statistics', 'federal', 'state',
            'government', 'administration', 'policy', 'regulation'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in gov_keywords)
    
    def _is_academic_claim(self, claim: str) -> bool:
        """Check if claim relates to academic research"""
        academic_keywords = [
            'study', 'research', 'paper', 'journal', 'scientist',
            'professor', 'university', 'peer-reviewed', 'published',
            'findings', 'evidence', 'data shows', 'according to research'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in academic_keywords)
    
    def _check_common_patterns(self, claim: str) -> Optional[Dict]:
        """Check common false claim patterns"""
        claim_lower = claim.lower()
        
        # Absolute statements that are usually false
        if re.search(r'\b(never|always|no one|everyone|all|none|every single|100%|0%)\b', claim_lower):
            if not re.search(r'\b\d+\s*%', claim):  # Unless it has specific percentages
                return self._create_verdict(
                    'mostly_false',
                    'Absolute claims are rarely accurate. Most situations have exceptions. Would need specific evidence to support such a sweeping statement.',
                    confidence=70
                )
        
        # "First time ever" claims
        if 'first time' in claim_lower or 'never before' in claim_lower:
            return self._create_verdict(
                'mostly_false',
                'Claims of unprecedented events are often incorrect. Similar events usually have historical precedents. Specific research into historical records would be needed to verify.',
                confidence=65
            )
        
        return None
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if claim is pure opinion without factual components"""
        # This method is deprecated in favor of _is_opinion_with_facts
        # Keep for compatibility but always return False to force analysis
        return False
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict string"""
        verdict_map = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mostly_true': 'mostly_true',
            'nearly true': 'nearly_true',
            'misleading': 'misleading',
            'mostly false': 'mostly_false',
            'mostly_false': 'mostly_false',
            'false': 'false',
            'needs context': 'needs_context',
            'needs_context': 'needs_context',
            'opinion': 'opinion',
            'mixed': 'mixed'
        }
        return verdict_map.get(verdict.lower().strip(), 'needs_context')
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 50, sources: List[str] = None) -> Dict:
        """Create standardized verdict"""
        return {
            'verdict': verdict,
            'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
            'explanation': explanation,
            'confidence': confidence,
            'sources': sources or [],
            'timestamp': datetime.now().isoformat()
        }

# Make it compatible with existing code
class FactChecker(ComprehensiveFactChecker):
    """Wrapper for compatibility"""
    pass
