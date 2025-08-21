"""
Enhanced Fact-Checking Service with Web Search Integration
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Enhanced verdict categories
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
    'intentionally_deceptive': {
        'label': 'Intentionally Deceptive',
        'icon': '🚨',
        'color': '#b91c1c',
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
    """Enhanced fact-checking service with web search"""
    
    def __init__(self, config):
        self.config = config
        self.google_api_key = getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None)
        self.openai_api_key = getattr(config, 'OPENAI_API_KEY', None)
        self.fred_api_key = getattr(config, 'FRED_API_KEY', None)
        self.news_api_key = getattr(config, 'NEWS_API_KEY', None)
        self.scraperapi_key = getattr(config, 'SCRAPERAPI_KEY', None)
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Expanded knowledge base for common facts
        self.knowledge_base = {
            'economic_facts': {
                'unemployment_rate': {
                    'ranges': {
                        '2020': {'low': 3.5, 'high': 14.8, 'context': 'COVID-19 pandemic'},
                        '2021': {'low': 3.9, 'high': 6.7},
                        '2022': {'low': 3.5, 'high': 4.0},
                        '2023': {'low': 3.4, 'high': 3.8},
                        '2024': {'low': 3.7, 'high': 4.1}
                    }
                },
                'inflation_rate': {
                    'ranges': {
                        '2021': {'annual': 4.7},
                        '2022': {'annual': 8.0, 'peak': 9.1},
                        '2023': {'annual': 4.1},
                        '2024': {'current': 3.2}
                    }
                }
            },
            'political_facts': {
                'trump_presidency': {'start': '2017-01-20', 'end': '2021-01-20'},
                'biden_presidency': {'start': '2021-01-20'},
                'trump_indictments': {'count': 4, 'year': 2023},
                'january_6': {'date': '2021-01-06', 'type': 'Capitol riot'}
            },
            'crime_statistics': {
                'violent_crime_trend': 'decreased overall since 1990s',
                'murder_rate_2020': 'increased by 30%',
                'murder_rate_2023': 'decreased by 13%'
            }
        }
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Check a claim and return enhanced verdict with explanation"""
        try:
            # Clean and analyze the claim
            claim = claim.strip()
            
            # Skip if too short
            if len(claim.split()) < 3:
                return self._create_verdict('opinion', 'Statement too short to fact-check')
            
            # Check if it's an opinion (but be less aggressive)
            if self._is_pure_opinion(claim):
                return self._create_verdict('opinion', 'This is a subjective opinion rather than a verifiable fact')
            
            # Try multiple fact-checking methods
            
            # 1. Check internal knowledge base first
            kb_result = self._check_knowledge_base_enhanced(claim)
            if kb_result:
                return kb_result
            
            # 2. Check for numerical claims
            numerical_result = self._check_numerical_claims(claim)
            if numerical_result:
                return numerical_result
            
            # 3. Try AI analysis if available
            if self.openai_client and self.config.ENABLE_AI_FACT_CHECKING:
                ai_result = self._check_with_ai_enhanced(claim, context)
                if ai_result and ai_result['verdict'] != 'needs_context':
                    return ai_result
            
            # 4. Check Google Fact Check API
            if self.google_api_key:
                google_result = self._check_google_fact_check(claim)
                if google_result:
                    return google_result
            
            # 5. Try web search for verification
            web_result = self._check_with_web_search(claim)
            if web_result and web_result['verdict'] != 'needs_context':
                return web_result
            
            # 6. Try pattern-based checking
            pattern_result = self._check_common_patterns(claim)
            if pattern_result:
                return pattern_result
            
            # If all else fails, provide a more informative "needs context" message
            return self._create_verdict(
                'needs_context',
                'Unable to verify this specific claim through available sources. It may be too recent or require specialized databases.'
            )
            
        except Exception as e:
            logger.error(f"Error checking claim: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    def _check_with_web_search(self, claim: str) -> Optional[Dict]:
        """Check claim using web search APIs"""
        try:
            # First try News API if available
            if self.news_api_key:
                news_result = self._search_news_api(claim)
                if news_result:
                    return news_result
            
            # Try ScraperAPI if available
            if self.scraperapi_key:
                scraper_result = self._search_with_scraperapi(claim)
                if scraper_result:
                    return scraper_result
            
            # If we have OpenAI, use it to analyze web search necessity
            if self.openai_client:
                return self._ai_web_search_analysis(claim)
                
        except Exception as e:
            logger.error(f"Web search error: {e}")
        
        return None
    
    def _search_news_api(self, claim: str) -> Optional[Dict]:
        """Search for claim verification using News API"""
        try:
            # Extract key terms from claim
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:5])
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.news_api_key,
                'q': search_query,
                'searchIn': 'title,description',
                'sortBy': 'relevancy',
                'pageSize': 10,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                if articles:
                    # Analyze articles for claim verification
                    return self._analyze_news_articles(claim, articles)
            
        except Exception as e:
            logger.error(f"News API error: {e}")
        
        return None
    
    def _analyze_news_articles(self, claim: str, articles: List[Dict]) -> Optional[Dict]:
        """Analyze news articles to verify claim"""
        try:
            # Count relevant articles
            relevant_count = 0
            supporting_count = 0
            contradicting_count = 0
            
            claim_lower = claim.lower()
            key_terms = self._extract_key_terms(claim)
            
            for article in articles[:5]:  # Analyze top 5 articles
                title = article.get('title', '').lower()
                description = article.get('description', '').lower()
                content = title + ' ' + description
                
                # Check relevance
                term_matches = sum(1 for term in key_terms if term.lower() in content)
                if term_matches >= 2:
                    relevant_count += 1
                    
                    # Simple sentiment analysis
                    if any(word in content for word in ['false', 'incorrect', 'misleading', 'debunked', 'wrong']):
                        contradicting_count += 1
                    elif any(word in content for word in ['true', 'correct', 'confirmed', 'verified', 'accurate']):
                        supporting_count += 1
            
            if relevant_count >= 3:
                if contradicting_count > supporting_count:
                    return self._create_verdict(
                        'mostly_false',
                        f'Found {relevant_count} news articles, majority suggest this claim is incorrect',
                        confidence=70,
                        sources=['News API Analysis']
                    )
                elif supporting_count > contradicting_count:
                    return self._create_verdict(
                        'mostly_true',
                        f'Found {relevant_count} news articles supporting this claim',
                        confidence=70,
                        sources=['News API Analysis']
                    )
                else:
                    return self._create_verdict(
                        'mixed',
                        f'Found {relevant_count} news articles with mixed information about this claim',
                        confidence=60,
                        sources=['News API Analysis']
                    )
            
        except Exception as e:
            logger.error(f"Error analyzing news articles: {e}")
        
        return None
    
    def _search_with_scraperapi(self, claim: str) -> Optional[Dict]:
        """Use ScraperAPI to search Google for claim verification"""
        try:
            search_query = quote(claim[:150])  # Limit query length
            url = f"http://api.scraperapi.com?api_key={self.scraperapi_key}&url=https://www.google.com/search?q={search_query}"
            
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                # Analyze Google search results
                content = response.text.lower()
                
                # Look for fact-checking indicators
                if 'fact check' in content:
                    if 'false' in content or 'incorrect' in content:
                        return self._create_verdict(
                            'false',
                            'Google search results indicate this claim has been fact-checked as false',
                            confidence=75,
                            sources=['Google Search']
                        )
                    elif 'true' in content or 'correct' in content:
                        return self._create_verdict(
                            'true',
                            'Google search results indicate this claim has been verified as true',
                            confidence=75,
                            sources=['Google Search']
                        )
                
        except Exception as e:
            logger.error(f"ScraperAPI error: {e}")
        
        return None
    
    def _ai_web_search_analysis(self, claim: str) -> Optional[Dict]:
        """Use AI to analyze if claim can be verified through web search"""
        try:
            prompt = f"""Analyze this claim and determine if it can be verified through web search:

Claim: "{claim}"

Consider:
1. Is this a factual claim that can be verified through news sources?
2. What type of sources would verify or debunk this claim?
3. Is this claim about recent events that would be in news articles?

If the claim CAN be verified through web search, respond with:
SEARCHABLE: YES
SEARCH_TERMS: [key terms to search]
EXPECTED_SOURCES: [types of sources that would have this information]

If it CANNOT be verified through general web search, respond with:
SEARCHABLE: NO
REASON: [why it cannot be verified through web search]"""

            response = self.openai_client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a fact-checking assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            if 'SEARCHABLE: YES' in result:
                return self._create_verdict(
                    'mostly_true',
                    'This claim appears to be verifiable through web sources. Manual verification recommended.',
                    confidence=60,
                    sources=['AI Analysis suggests web verification possible']
                )
            
        except Exception as e:
            logger.error(f"AI web search analysis error: {e}")
        
        return None
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key search terms from claim"""
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
                     'could', 'may', 'might', 'must', 'shall', 'can', 'said', 'says', 'told'}
        
        # Extract words
        words = re.findall(r'\b\w+\b', claim)
        key_terms = []
        
        # Prioritize: 1) Proper nouns, 2) Numbers, 3) Uncommon words
        for word in words:
            if word[0].isupper() and word.lower() not in stop_words:
                key_terms.append(word)
        
        # Add numbers
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        key_terms.extend(numbers)
        
        # Add remaining significant words
        for word in words:
            if (word.lower() not in stop_words and 
                word not in key_terms and 
                len(word) > 3):
                key_terms.append(word)
        
        return key_terms[:10]  # Limit to 10 terms
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if a claim is purely opinion (be less aggressive)"""
        claim_lower = claim.lower()
        
        # Strong opinion indicators
        strong_opinion_phrases = [
            'i think', 'i believe', 'i feel', 'in my opinion',
            'i hope', 'i wish', 'i want', 'i prefer'
        ]
        
        for phrase in strong_opinion_phrases:
            if phrase in claim_lower:
                return True
        
        # Don't mark as opinion just because it has "should" or "best"
        # These could be policy claims that can be fact-checked
        
        return False
    
    def _check_knowledge_base_enhanced(self, claim: str) -> Optional[Dict]:
        """Enhanced knowledge base checking"""
        claim_lower = claim.lower()
        
        # Check unemployment claims
        if 'unemployment' in claim_lower:
            for year in ['2020', '2021', '2022', '2023', '2024']:
                if year in claim:
                    # Extract percentage
                    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', claim)
                    if percent_match:
                        claimed_rate = float(percent_match.group(1))
                        actual_data = self.knowledge_base['economic_facts']['unemployment_rate']['ranges'].get(year)
                        
                        if actual_data:
                            if actual_data['low'] <= claimed_rate <= actual_data['high']:
                                return self._create_verdict(
                                    'true',
                                    f'The unemployment rate in {year} did reach approximately {claimed_rate}%',
                                    confidence=90
                                )
                            else:
                                return self._create_verdict(
                                    'false',
                                    f'The unemployment rate in {year} ranged from {actual_data["low"]}% to {actual_data["high"]}%, not {claimed_rate}%',
                                    confidence=90
                                )
        
        # Check inflation claims
        if 'inflation' in claim_lower:
            for year, data in self.knowledge_base['economic_facts']['inflation_rate']['ranges'].items():
                if year in claim:
                    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', claim)
                    if percent_match:
                        claimed_rate = float(percent_match.group(1))
                        
                        if 'annual' in data:
                            if abs(claimed_rate - data['annual']) < 0.5:
                                return self._create_verdict(
                                    'true',
                                    f'The inflation rate in {year} was approximately {data["annual"]}%',
                                    confidence=85
                                )
                            elif abs(claimed_rate - data['annual']) < 1.5:
                                return self._create_verdict(
                                    'mostly_true',
                                    f'The inflation rate in {year} was {data["annual"]}%, close to the claimed {claimed_rate}%',
                                    confidence=80
                                )
        
        # Check crime statistics
        if 'crime' in claim_lower or 'murder' in claim_lower:
            if '2020' in claim and ('increase' in claim_lower or 'up' in claim_lower):
                if '30' in claim or 'thirty' in claim_lower:
                    return self._create_verdict(
                        'true',
                        'The murder rate did increase by approximately 30% in 2020',
                        confidence=85
                    )
            
            if 'violent crime' in claim_lower and ('down' in claim_lower or 'decrease' in claim_lower):
                return self._create_verdict(
                    'mostly_true',
                    'Violent crime has generally decreased since the 1990s, though with year-to-year variations',
                    confidence=80
                )
        
        return None
    
    def _check_numerical_claims(self, claim: str) -> Optional[Dict]:
        """Check claims with specific numbers"""
        # Look for numerical patterns
        number_patterns = [
            (r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion)', 'large_number'),
            (r'(\d+(?:\.\d+)?)\s*(?:percent|%)', 'percentage'),
            (r'\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion|trillion)?', 'money'),
            (r'(\d{4})', 'year')
        ]
        
        for pattern, num_type in number_patterns:
            matches = re.findall(pattern, claim, re.IGNORECASE)
            if matches and num_type == 'percentage':
                # For percentages, check if they're reasonable
                for match in matches:
                    value = float(match)
                    if value > 100:
                        return self._create_verdict(
                            'false',
                            f'The claim mentions {value}%, which is impossible as percentages cannot exceed 100%',
                            confidence=95
                        )
        
        return None
    
    def _check_common_patterns(self, claim: str) -> Optional[Dict]:
        """Check common claim patterns"""
        claim_lower = claim.lower()
        
        # Common false claim patterns
        false_patterns = [
            ('never been done before', 'This claim of unprecedented action is often inaccurate'),
            ('first time in history', 'Historical "first" claims are frequently incorrect'),
            ('nobody has ever', 'Absolute claims about what has never happened are usually false'),
            ('everyone knows', 'Universal knowledge claims are typically exaggerated'),
            ('100% of', 'Claims of 100% are almost always false or exaggerated'),
            ('0% of', 'Claims of 0% are almost always false or exaggerated')
        ]
        
        for pattern, explanation in false_patterns:
            if pattern in claim_lower:
                return self._create_verdict(
                    'mostly_false',
                    f'{explanation}. Such absolute statements are rarely accurate.',
                    confidence=70
                )
        
        # Common exaggeration patterns
        exaggeration_patterns = [
            ('biggest ever', 'Claims of being the "biggest ever" are often exaggerations'),
            ('worst ever', 'Claims of being the "worst ever" are often exaggerations'),
            ('best ever', 'Claims of being the "best ever" are often exaggerations'),
            ('most successful', 'Superlative claims often lack proper context')
        ]
        
        for pattern, explanation in exaggeration_patterns:
            if pattern in claim_lower:
                return self._create_verdict(
                    'exaggeration',
                    explanation,
                    confidence=65
                )
        
        return None
    
    def _check_with_ai_enhanced(self, claim: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """Enhanced AI checking with better prompts"""
        try:
            prompt = f"""You are a professional fact-checker. Analyze this claim and provide a verdict.

Important: Be decisive. Only use "needs_context" if the claim is truly impossible to evaluate.
For most claims, you should be able to determine if they are true, false, or misleading based on general knowledge up to early 2024.

Claim: "{claim}"

Provide your analysis in this format:
VERDICT: [Choose: TRUE, MOSTLY_TRUE, EXAGGERATION, MISLEADING, MOSTLY_FALSE, FALSE, or NEEDS_CONTEXT]
CONFIDENCE: [0-100]
EXPLANATION: [Brief explanation of why this verdict was chosen]
EVIDENCE: [Key facts that support your verdict]"""

            response = self.openai_client.chat.completions.create(
                model=getattr(self.config, 'OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": "You are a professional fact-checker. Be decisive and accurate."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            verdict_match = re.search(r'VERDICT:\s*(\w+)', result)
            confidence_match = re.search(r'CONFIDENCE:\s*(\d+)', result)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:EVIDENCE:|$)', result, re.DOTALL)
            evidence_match = re.search(r'EVIDENCE:\s*(.+)$', result, re.DOTALL)
            
            if verdict_match and explanation_match:
                verdict = self._normalize_verdict(verdict_match.group(1))
                confidence = int(confidence_match.group(1)) if confidence_match else 70
                explanation = explanation_match.group(1).strip()
                
                if evidence_match:
                    explanation += f" Evidence: {evidence_match.group(1).strip()}"
                
                return self._create_verdict(verdict, explanation, confidence, ['AI Analysis'])
                
        except Exception as e:
            logger.error(f"AI fact-checking error: {e}")
        
        return None
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 50, sources: List[str] = None) -> Dict:
        """Create a standardized verdict response"""
        return {
            'verdict': verdict,
            'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
            'explanation': explanation,
            'confidence': confidence,
            'sources': sources or [],
            'ai_analysis_used': 'AI Analysis' in (sources or [])
        }
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict string to standard format"""
        verdict_lower = verdict.lower().strip()
        
        mappings = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mostly_true': 'mostly_true',
            'nearly true': 'nearly_true',
            'exaggeration': 'exaggeration',
            'exaggerated': 'exaggeration',
            'misleading': 'misleading',
            'mostly false': 'mostly_false',
            'mostly_false': 'mostly_false',
            'false': 'false',
            'needs_context': 'needs_context',
            'needs context': 'needs_context',
            'opinion': 'opinion',
            'mixed': 'misleading'
        }
        
        return mappings.get(verdict_lower, 'needs_context')
    
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
            'lacks context': 'needs_context',
            'unproven': 'needs_context',
            'exaggerated': 'exaggeration'
        }
        
        for key, value in mappings.items():
            if key in rating_lower:
                return value
        
        return 'needs_context'
    
    # Keep the original methods for compatibility
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
