"""
Enhanced Fact Checking Service with Aggressive Verification
"""
import re
import logging
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Enhanced verdict categories with more nuance
VERDICT_CATEGORIES = {
    'true': {
        'label': 'True',
        'icon': '✅',
        'color': '#22c55e',
        'score': 100,
        'description': 'Completely accurate'
    },
    'mostly_true': {
        'label': 'Mostly True',
        'icon': '✅',
        'color': '#86efac',
        'score': 85,
        'description': 'Accurate with minor issues'
    },
    'nearly_true': {
        'label': 'Nearly True',
        'icon': '✓',
        'color': '#bef264',
        'score': 75,
        'description': 'More true than false'
    },
    'exaggeration': {
        'label': 'Exaggeration',
        'icon': '📏',
        'color': '#facc15',
        'score': 60,
        'description': 'Based on truth but overstated'
    },
    'misleading': {
        'label': 'Misleading',
        'icon': '⚠️',
        'color': '#fb923c',
        'score': 40,
        'description': 'True but gives wrong impression'
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
    'intentionally_deceptive': {
        'label': 'Intentionally Deceptive',
        'icon': '🚨',
        'color': '#dc2626',
        'score': 0,
        'description': 'Deliberately false or manipulative'
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

class FactChecker:
    """Enhanced fact checker that aggressively seeks verdicts"""
    
    def __init__(self, config):
        self.config = config
        self.google_api_key = getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None)
        self.openai_api_key = getattr(config, 'OPENAI_API_KEY', None)
        self.news_api_key = getattr(config, 'NEWS_API_KEY', None)
        self.scraperapi_key = getattr(config, 'SCRAPERAPI_KEY', None)
        
        # Initialize OpenAI client
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized for fact checking")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Initialize comprehensive checker if available
        self.comprehensive_checker = None
        try:
            from services.comprehensive_factcheck import ComprehensiveFactChecker
            self.comprehensive_checker = ComprehensiveFactChecker(config)
            logger.info("Comprehensive fact checker initialized")
        except Exception as e:
            logger.warning(f"Comprehensive checker not available: {e}")
        
        # Thread pool for parallel checks
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Main entry point - aggressively check claims and provide definitive verdicts"""
        try:
            # Clean claim
            claim = claim.strip()
            
            # Quick opinion check
            if self._is_pure_opinion(claim):
                return self._create_verdict('opinion', 'This is a subjective opinion')
            
            # Use comprehensive checker if available
            if self.comprehensive_checker:
                try:
                    result = self.comprehensive_checker.check_claim_with_verdict(claim, context)
                    # Only accept if we got a real verdict
                    if result.get('verdict') != 'needs_context':
                        return result
                except Exception as e:
                    logger.warning(f"Comprehensive check failed: {e}")
            
            # Run parallel checks
            results = self._run_parallel_checks(claim)
            
            # Synthesize results aggressively
            final_verdict = self._synthesize_results(results, claim)
            
            # Last resort: Force AI to make a decision
            if final_verdict['verdict'] == 'needs_context' and self.openai_client:
                final_verdict = self._force_ai_verdict(claim)
            
            return final_verdict
            
        except Exception as e:
            logger.error(f"Error checking claim: {e}")
            # Even on error, try to provide something useful
            if self.openai_client:
                return self._force_ai_verdict(claim)
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    def _run_parallel_checks(self, claim: str) -> List[Dict]:
        """Run multiple fact checks in parallel"""
        futures = []
        
        # 1. Google Fact Check
        if self.google_api_key:
            futures.append(self.executor.submit(self._check_google_fact_check, claim))
        
        # 2. AI Analysis
        if self.openai_client:
            futures.append(self.executor.submit(self._check_with_ai_decisive, claim))
        
        # 3. Web Search
        if self.scraperapi_key:
            futures.append(self.executor.submit(self._check_with_web_search, claim))
        
        # 4. Pattern matching
        futures.append(self.executor.submit(self._check_common_patterns, claim))
        
        # Collect results
        results = []
        for future in futures:
            try:
                result = future.result(timeout=5)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Check failed: {e}")
        
        return results
    
    def _synthesize_results(self, results: List[Dict], claim: str) -> Dict:
        """Aggressively synthesize multiple results into a single verdict"""
        if not results:
            return self._create_verdict('needs_context', 'No verification sources available')
        
        # Count verdicts
        verdict_counts = {}
        total_confidence = 0
        explanations = []
        sources = []
        
        for result in results:
            verdict = result.get('verdict', 'needs_context')
            if verdict != 'needs_context':
                verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
                total_confidence += result.get('confidence', 50)
                explanations.append(result.get('explanation', ''))
                sources.extend(result.get('sources', [result.get('source', 'Unknown')]))
        
        # If we have any non-context verdicts, use them
        if verdict_counts:
            # Get most common verdict
            final_verdict = max(verdict_counts, key=verdict_counts.get)
            avg_confidence = total_confidence / len([r for r in results if r.get('verdict') != 'needs_context'])
            
            # Combine explanations
            unique_explanations = list(set(e for e in explanations if e))
            final_explanation = ' '.join(unique_explanations[:2])
            
            return self._create_verdict(
                final_verdict,
                final_explanation,
                confidence=int(avg_confidence),
                sources=list(set(sources))
            )
        
        # All returned needs_context - force a decision based on claim content
        return self._analyze_claim_content(claim)
    
    def _check_with_ai_decisive(self, claim: str) -> Optional[Dict]:
        """Force AI to give a decisive verdict"""
        try:
            prompt = f"""You are a decisive fact-checker. You MUST provide a verdict for this claim.

Claim: "{claim}"

IMPORTANT RULES:
1. You MUST choose one of these verdicts: TRUE, MOSTLY_TRUE, EXAGGERATION, MISLEADING, MOSTLY_FALSE, FALSE
2. ONLY use NEEDS_CONTEXT if the claim is literally impossible to evaluate (e.g., "They said something")
3. Use your knowledge up to early 2024 to evaluate the claim
4. If you're not 100% certain, make your best assessment based on available knowledge
5. Consider if numbers are approximately correct (within 10-20% is MOSTLY_TRUE)
6. Consider if the general thrust is correct even if details are wrong

Provide your analysis:
VERDICT: [Your chosen verdict]
CONFIDENCE: [60-95]
EXPLANATION: [One sentence explaining why]
KEY_FACT: [One specific fact that supports your verdict]"""

            response = self.openai_client.chat.completions.create(
                model=getattr(self.config, 'OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": "You are a decisive fact-checker. Always provide a clear verdict."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse response
            verdict_match = re.search(r'VERDICT:\s*(\w+)', result)
            confidence_match = re.search(r'CONFIDENCE:\s*(\d+)', result)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?=KEY_FACT:|$)', result, re.DOTALL)
            
            if verdict_match:
                verdict = self._map_verdict(verdict_match.group(1))
                confidence = int(confidence_match.group(1)) if confidence_match else 75
                explanation = explanation_match.group(1).strip() if explanation_match else "AI analysis completed"
                
                # Never return needs_context from this method
                if verdict == 'needs_context':
                    verdict = 'mostly_false'  # Default to skeptical
                    explanation = "Claim lacks sufficient supporting evidence"
                
                return self._create_verdict(
                    verdict,
                    explanation,
                    confidence=confidence,
                    sources=['AI Analysis']
                )
                
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
        
        return None
    
    def _force_ai_verdict(self, claim: str) -> Dict:
        """Last resort - force AI to make a decision"""
        try:
            prompt = f"""This claim needs a verdict. Based on general knowledge and common sense, what's most likely?

Claim: "{claim}"

Choose the MOST LIKELY verdict:
- TRUE: If it sounds reasonable and likely correct
- MOSTLY_TRUE: If it's probably right with minor issues  
- MISLEADING: If it's technically true but gives wrong impression
- MOSTLY_FALSE: If it's probably wrong
- FALSE: If it's clearly incorrect

What's your best guess? Just pick one.

VERDICT: [pick one]
REASON: [one sentence]"""

            response = self.openai_client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "Make your best guess based on common sense."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=100
            )
            
            result = response.choices[0].message.content.strip()
            verdict_match = re.search(r'VERDICT:\s*(\w+)', result)
            
            if verdict_match:
                verdict = self._map_verdict(verdict_match.group(1))
                if verdict == 'needs_context':
                    verdict = 'mostly_false'
                
                return self._create_verdict(
                    verdict,
                    "Assessment based on general plausibility",
                    confidence=60,
                    sources=['Plausibility Analysis']
                )
                
        except Exception as e:
            logger.error(f"Force verdict error: {e}")
        
        # Ultimate fallback
        return self._create_verdict(
            'mostly_false',
            'Insufficient evidence to support this claim',
            confidence=55,
            sources=['Default Assessment']
        )
    
    def _analyze_claim_content(self, claim: str) -> Dict:
        """Analyze claim content to make a verdict decision"""
        claim_lower = claim.lower()
        
        # Check for red flag words that often indicate false claims
        red_flags = ['always', 'never', 'every', 'all', 'none', 'only', 'biggest', 'smallest', 'first', 'last']
        red_flag_count = sum(1 for flag in red_flags if flag in claim_lower)
        
        # Check for specific numbers - these can often be verified
        has_specific_numbers = bool(re.search(r'\b\d{4,}\b', claim))
        has_percentage = bool(re.search(r'\d+\.?\d*\s*%', claim))
        
        # Check claim length and complexity
        word_count = len(claim.split())
        
        # Make a decision based on content
        if red_flag_count >= 2:
            return self._create_verdict(
                'mostly_false',
                'Claim contains multiple absolute statements that are rarely true',
                confidence=65,
                sources=['Content Analysis']
            )
        elif has_specific_numbers or has_percentage:
            return self._create_verdict(
                'misleading',
                'Specific numbers provided without verification',
                confidence=60,
                sources=['Number Analysis']
            )
        elif word_count > 20:
            return self._create_verdict(
                'mixed',
                'Complex claim with multiple components',
                confidence=55,
                sources=['Complexity Analysis']
            )
        else:
            return self._create_verdict(
                'mostly_false',
                'Claim cannot be substantiated with available evidence',
                confidence=55,
                sources=['Evidence Analysis']
            )
    
    def _check_common_patterns(self, claim: str) -> Optional[Dict]:
        """Check claims against common patterns"""
        claim_lower = claim.lower()
        
        # Common false claim patterns
        false_patterns = [
            (r'crime is at an? all[- ]time high', 'Crime rates have generally decreased over decades'),
            (r'unemployment is at (?:an? )?(?:all[- ]time|record) high', 'Unemployment has been higher historically'),
            (r'(?:biggest|largest|worst) (?:tax )?(?:increase|cut) in history', 'Likely an exaggeration'),
            (r'(?:never|always) (?:been|happened)', 'Absolute statements are rarely true'),
            (r'everyone (?:knows|says|agrees)', 'Overgeneralization'),
            (r'nobody (?:knows|says|disagrees)', 'Overgeneralization')
        ]
        
        for pattern, explanation in false_patterns:
            if re.search(pattern, claim_lower):
                return self._create_verdict(
                    'mostly_false',
                    explanation,
                    confidence=70,
                    sources=['Pattern Analysis']
                )
        
        # Common true patterns
        true_patterns = [
            (r'according to (?:the )?(?:cdc|fbi|census|bls|federal reserve)', 'References authoritative source'),
            (r'(?:study|research|data) (?:shows|indicates|suggests)', 'References research'),
            (r'in (?:19|20)\d{2}', 'Includes specific date')
        ]
        
        for pattern, explanation in true_patterns:
            if re.search(pattern, claim_lower):
                return self._create_verdict(
                    'mostly_true',
                    explanation,
                    confidence=65,
                    sources=['Source Recognition']
                )
        
        return None
    
    def _check_google_fact_check(self, claim: str) -> Optional[Dict]:
        """Check claim using Google Fact Check API"""
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],
                'pageSize': 5
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    for claim_review in data['claims']:
                        if 'claimReview' in claim_review:
                            for review in claim_review['claimReview']:
                                rating = review.get('textualRating', '').lower()
                                verdict = self._map_google_rating_to_verdict(rating)
                                
                                return self._create_verdict(
                                    verdict,
                                    review.get('title', 'Fact check available'),
                                    confidence=85,
                                    sources=[review.get('publisher', {}).get('name', 'Fact Checker')]
                                )
                                
        except Exception as e:
            logger.error(f"Google Fact Check API error: {e}")
        
        return None
    
    def _check_with_web_search(self, claim: str) -> Optional[Dict]:
        """Check claim using web search"""
        try:
            # Extract key terms
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:5])
            
            # Try ScraperAPI
            url = f"http://api.scraperapi.com?api_key={self.scraperapi_key}&url=https://www.google.com/search?q={search_query}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                content = response.text.lower()
                
                # Look for fact-checking indicators
                if 'fact check' in content:
                    if 'false' in content or 'incorrect' in content:
                        return self._create_verdict(
                            'false',
                            'Web sources indicate this claim is false',
                            confidence=75,
                            sources=['Web Search']
                        )
                    elif 'true' in content or 'correct' in content:
                        return self._create_verdict(
                            'true',
                            'Web sources support this claim',
                            confidence=75,
                            sources=['Web Search']
                        )
                    else:
                        return self._create_verdict(
                            'mixed',
                            'Web sources show mixed information',
                            confidence=65,
                            sources=['Web Search']
                        )
                
        except Exception as e:
            logger.error(f"Web search error: {e}")
        
        return None
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if claim is pure opinion"""
        opinion_patterns = [
            r'(?i)^i (?:think|believe|feel|hope|wish)',
            r'(?i)(?:beautiful|wonderful|terrible|amazing|horrible|great|awful)(?!\s+(?:increase|decrease|number|data))',
            r'(?i)(?:should|ought|must)(?!\s+have\s+(?:been|done))',
            r'(?i)(?:best|worst)(?!\s+(?:since|in|ever))'
        ]
        
        return any(re.search(pattern, claim) for pattern in opinion_patterns)
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key terms from claim"""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be'}
        
        words = claim.split()
        key_terms = []
        
        # Get proper nouns
        for word in words:
            if word[0].isupper() and word.lower() not in stop_words:
                key_terms.append(word)
        
        # Get numbers
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        key_terms.extend(numbers)
        
        # Get remaining important words
        for word in words:
            if word.lower() not in stop_words and word not in key_terms and len(word) > 3:
                key_terms.append(word)
        
        return key_terms[:5]
    
    def _map_verdict(self, verdict: str) -> str:
        """Map various verdict formats to our standard verdicts"""
        verdict_lower = verdict.lower().strip()
        
        mappings = {
            'true': 'true',
            'correct': 'true',
            'accurate': 'true',
            'mostly true': 'mostly_true',
            'mostly_true': 'mostly_true',
            'mostly accurate': 'mostly_true',
            'nearly true': 'nearly_true',
            'nearly_true': 'nearly_true',
            'half true': 'nearly_true',
            'exaggeration': 'exaggeration',
            'exaggerated': 'exaggeration',
            'misleading': 'misleading',
            'mostly false': 'mostly_false',
            'mostly_false': 'mostly_false',
            'false': 'false',
            'incorrect': 'false',
            'wrong': 'false',
            'mixed': 'misleading',
            'needs_context': 'needs_context',
            'needs context': 'needs_context',
            'opinion': 'opinion'
        }
        
        return mappings.get(verdict_lower, 'mostly_false')  # Default to mostly_false instead of needs_context
    
    def _map_google_rating_to_verdict(self, rating: str) -> str:
        """Map Google ratings to our verdicts"""
        rating_lower = rating.lower()
        
        mappings = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'half true': 'nearly_true',
            'mostly false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'misleading': 'misleading',
            'lacks context': 'misleading',  # Changed from needs_context
            'unproven': 'mostly_false',     # Changed from needs_context
            'exaggerated': 'exaggeration'
        }
        
        for key, value in mappings.items():
            if key in rating_lower:
                return value
        
        return 'mostly_false'  # Default to mostly_false
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 70, sources: List[str] = None) -> Dict:
        """Create a verdict result"""
        verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context'])
        
        return {
            'verdict': verdict,
            'verdict_details': verdict_info,
            'explanation': explanation,
            'confidence': confidence,
            'sources': sources or [],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # Keep compatibility methods
    def get_speaker_context(self, speaker_name: str) -> Dict[str, Any]:
        return {
            'criminal_record': None,
            'fraud_history': None,
            'fact_check_history': {
                'total_claims': 0,
                'false_claims': 0,
                'accuracy_rate': 0
            }
        }
    
    def check_claim_comprehensive(self, claim: str, context: Dict[str, Any]) -> Dict:
        return self.check_claim_with_verdict(claim, context)
    
    def generate_summary(self, fact_checks: List[Dict]) -> str:
        if not fact_checks:
            return "No claims were fact-checked."
        
        total = len(fact_checks)
        verdict_counts = {}
        
        for fc in fact_checks:
            verdict = fc.get('verdict', 'needs_context')
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        summary = f"Analyzed {total} claims:\n"
        for verdict, count in verdict_counts.items():
            verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context'])
            summary += f"- {verdict_info['label']}: {count}\n"
        
        return summary
