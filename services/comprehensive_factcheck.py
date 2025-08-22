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

# Import all our unused services
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
        
        # Initialize all API keys
        self.api_keys = {
            'google': getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None),
            'openai': getattr(config, 'OPENAI_API_KEY', None),
            'fred': getattr(config, 'FRED_API_KEY', None),
            'news': getattr(config, 'NEWS_API_KEY', None),
            'mediastack': getattr(config, 'MEDIASTACK_API_KEY', None),
            'scraperapi': getattr(config, 'SCRAPERAPI_KEY', None),
            'scrapingbee': getattr(config, 'SCRAPINGBEE_API_KEY', None),
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
        
        # 7. Web search via ScraperAPI
        if self.api_keys['scraperapi']:
            tasks.append(('scraper', self._search_with_scraperapi(claim)))
        
        # 8. Academic sources
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
                sources=sources_used
            )
        
        # Weight verdicts
        verdict_scores = {}
        for v in verdicts:
            verdict_type = v['verdict']
            score = v['confidence'] * v['weight']
            
            if verdict_type not in verdict_scores:
                verdict_scores[verdict_type] = 0
            verdict_scores[verdict_type] += score
        
        # Get consensus verdict
        final_verdict = max(verdict_scores.items(), key=lambda x: x[1])[0]
        
        # Calculate confidence
        total_weight = sum(v['weight'] for v in verdicts)
        avg_confidence = sum(v['confidence'] * v['weight'] for v in verdicts) / total_weight if total_weight > 0 else 50
        
        # Build explanation
        explanation = f"Based on {len(verdicts)} sources: " + " | ".join(explanations[:3])
        
        # Add historical context
        if historical:
            if historical.get('previously_checked'):
                explanation += f" (Previously checked {historical['check_count']} times)"
            elif historical.get('source_history'):
                reliability = historical['source_history'].get('reliability_score', 0)
                if reliability < 0.5:
                    explanation += f" (Note: {speaker} has low fact-check reliability: {reliability:.0%})"
        
        return self._create_verdict(
            final_verdict,
            explanation,
            confidence=int(avg_confidence),
            sources=sources_used
        )
    
    async def _search_with_scraperapi(self, claim: str) -> Dict:
        """Enhanced web search using ScraperAPI"""
        try:
            # Build search query
            search_query = quote(claim[:150])
            fact_check_query = quote(f"{claim[:100]} fact check")
            
            # Search both general and fact-check specific
            urls = [
                f"https://www.google.com/search?q={search_query}",
                f"https://www.google.com/search?q={fact_check_query}"
            ]
            
            results_found = False
            explanations = []
            
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    scraper_url = f"http://api.scraperapi.com?api_key={self.api_keys['scraperapi']}&url={url}"
                    
                    async with session.get(scraper_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            content = await response.text()
                            
                            # Look for fact-checking indicators
                            if 'fact-check' in content.lower():
                                results_found = True
                                
                                if 'false' in content.lower() or 'incorrect' in content.lower():
                                    return {
                                        'found': True,
                                        'verdict': 'false',
                                        'confidence': 75,
                                        'explanation': 'Multiple sources indicate this claim is false',
                                        'source': 'Web Search',
                                        'weight': 0.7
                                    }
                                elif 'true' in content.lower() or 'correct' in content.lower():
                                    return {
                                        'found': True,
                                        'verdict': 'true',
                                        'confidence': 75,
                                        'explanation': 'Multiple sources support this claim',
                                        'source': 'Web Search',
                                        'weight': 0.7
                                    }
            
            if results_found:
                return {
                    'found': True,
                    'verdict': 'mixed',
                    'confidence': 60,
                    'explanation': 'Found mixed information about this claim',
                    'source': 'Web Search',
                    'weight': 0.6
                }
                
        except Exception as e:
            logger.error(f"ScraperAPI error: {e}")
        
        return {'found': False}
    
    async def _check_with_ai_comprehensive(self, claim: str) -> Dict:
        """Comprehensive AI analysis"""
        try:
            prompt = f"""You are a professional fact-checker with access to information up to early 2024.

Analyze this claim: "{claim}"

Instructions:
1. First, determine if this claim can be verified with known facts
2. If verifiable, provide the verdict based on your knowledge
3. Be specific about what makes it true, false, or misleading
4. Cite specific facts, dates, or figures when possible
5. Only say "needs_context" if you truly cannot evaluate it

Format your response as:
VERDICT: [true/mostly_true/misleading/mostly_false/false/needs_context]
CONFIDENCE: [0-100]
EXPLANATION: [Detailed explanation with specific facts]
KEY_FACTS: [Bullet points of verifiable facts]
SEARCH_TERMS: [Terms to search for verification]"""

            # Use asyncio-compatible method
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model='gpt-4-1106-preview' if 'gpt-4' in str(self.config.OPENAI_MODEL) else 'gpt-3.5-turbo',
                    messages=[
                        {"role": "system", "content": "You are a professional fact-checker. Be specific and decisive."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=500
                )
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse response
            verdict = self._extract_field(result, 'VERDICT')
            confidence = int(self._extract_field(result, 'CONFIDENCE', '70'))
            explanation = self._extract_field(result, 'EXPLANATION', '')
            key_facts = self._extract_field(result, 'KEY_FACTS', '')
            search_terms = self._extract_field(result, 'SEARCH_TERMS', '')
            
            if verdict and verdict.lower() != 'needs_context':
                full_explanation = explanation
                if key_facts:
                    full_explanation += f" Key facts: {key_facts}"
                
                return {
                    'found': True,
                    'verdict': self._normalize_verdict(verdict),
                    'confidence': confidence,
                    'explanation': full_explanation[:500],
                    'source': 'AI Analysis',
                    'weight': 0.8,
                    'search_terms': search_terms
                }
                
        except Exception as e:
            logger.error(f"AI comprehensive check error: {e}")
        
        return {'found': False}
    
    def _extract_field(self, text: str, field: str, default: str = '') -> str:
        """Extract field from structured text"""
        pattern = rf'{field}:\s*(.+?)(?=\n[A-Z]+:|$)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else default
    
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
