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
        'label': 'Opinion',
        'icon': '💭',
        'color': '#6366f1',
        'score': None,
        'description': 'Subjective statement, not a factual claim'
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
            
            # Skip if too short or opinion
            if len(claim.split()) < 4:
                return self._create_verdict('opinion', 'Statement too short to fact-check')
            
            if self._is_pure_opinion(claim):
                return self._create_verdict('opinion', 'This is a subjective opinion')
            
            # Resolve context (pronouns, references)
            if context and context.get('transcript'):
                self.context_resolver.analyze_full_transcript(context['transcript'])
            
            resolved_claim, context_info = self.context_resolver.resolve_context(claim)
            if resolved_claim != claim:
                logger.info(f"Resolved claim: {claim} -> {resolved_claim}")
                claim = resolved_claim
            
            # Check if claim is too vague
            vagueness = self.context_resolver.is_claim_too_vague(claim)
            if vagueness['is_vague']:
                return self._create_verdict('needs_context', vagueness['reason'])
            
            # Check historical patterns
            speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            historical = self.fact_history.get_historical_context(claim, speaker)
            
            # Run comprehensive fact-checking
            result = asyncio.run(self._comprehensive_check(claim, speaker, historical))
            
            # Add to history
            self.fact_history.add_check(claim, speaker, result['verdict'], result['explanation'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fact-check: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    async def _comprehensive_check(self, claim: str, speaker: str, historical: Optional[Dict]) -> Dict:
        """Run all fact-checking methods in parallel"""
        
        # Create tasks for all API checks
        tasks = []
        
        # 1. Google Fact Check
        if self.api_keys['google']:
            tasks.append(('google', self.api_checkers.check_google_factcheck(claim)))
        
        # 2. AI Analysis
        if self.openai_client:
            tasks.append(('ai', self._check_with_ai_comprehensive(claim)))
        
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
        
        # Build explanation
        explanation = ' '.join(explanations) if explanations else 'Based on available evidence.'
        
        # Add historical context
        if historical and historical.get('pattern'):
            explanation += f" Note: {speaker} has a pattern of {historical['pattern']}."
        
        return self._create_verdict(
            final_verdict,
            explanation,
            confidence=avg_confidence,
            sources=sources_used
        )
    
    async def _check_with_ai_comprehensive(self, claim: str) -> Dict:
        """Use AI for comprehensive fact-checking"""
        try:
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
                    {"role": "system", "content": "You are a fact-checker. Be objective and accurate."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            
            # Parse response
            verdict = 'needs_context'
            if 'TRUE' in result.upper():
                verdict = 'true'
            elif 'FALSE' in result.upper():
                verdict = 'false'
            elif 'MIXED' in result.upper() or 'PARTIALLY' in result.upper():
                verdict = 'mixed'
            
            # Extract explanation
            explanation = self._extract_explanation(result)
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
    
    def _extract_explanation(self, text: str, default: str = "See analysis") -> str:
        """Extract explanation from text"""
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
            'immigration', 'crime', 'statistics', 'federal', 'state'
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
                    'Absolute claims are rarely accurate. Most situations have exceptions.',
                    confidence=70
                )
        
        # "First time ever" claims
        if 'first time' in claim_lower or 'never before' in claim_lower:
            return self._create_verdict(
                'mostly_false',
                'Claims of unprecedented events are often incorrect. Similar events usually have historical precedents.',
                confidence=65
            )
        
        return None
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if claim is pure opinion"""
        opinion_phrases = [
            'i think', 'i believe', 'i feel', 'in my opinion',
            'seems to me', 'appears to be', 'looks like'
        ]
        claim_lower = claim.lower()
        return any(phrase in claim_lower for phrase in opinion_phrases)
    
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
            'opinion': 'opinion'
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
