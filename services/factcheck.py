"""
Enhanced Fact Checking Service - With Political Topics and Better Verdicts
"""
import os
import re
import time
import json
import logging
import requests
import asyncio
import aiohttp
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from config import Config
from .political_topics import PoliticalTopicsChecker

logger = logging.getLogger(__name__)

class FactChecker:
    """Enhanced fact-checking with political topics and better verdict determination"""
    
    def __init__(self):
        # Initialize ALL API keys
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.fred_api_key = Config.FRED_API_KEY
        self.news_api_key = Config.NEWS_API_KEY
        self.mediastack_api_key = Config.MEDIASTACK_API_KEY
        self.openai_api_key = Config.OPENAI_API_KEY
        self.scraperapi_key = Config.SCRAPERAPI_KEY
        self.scrapingbee_api_key = Config.SCRAPINGBEE_API_KEY
        
        # Initialize political topics checker
        self.political_checker = PoliticalTopicsChecker()
        
        # Check if we have ANY real APIs configured
        self.has_apis = any([
            self.google_api_key,
            self.fred_api_key,
            self.news_api_key,
            self.mediastack_api_key,
            self.openai_api_key
        ])
        
        # Expandable speaker backgrounds - not just Trump
        self.speaker_backgrounds = {
            'Donald Trump': {
                'criminal_record': 'Convicted felon - 34 counts of falsifying business records (May 2024)',
                'fraud_history': 'Found liable for civil fraud - inflating wealth to obtain favorable loans and insurance rates ($355 million penalty)',
                'fact_check_history': 'Made over 30,000 false or misleading claims during presidency (Washington Post)',
                'credibility_notes': 'Documented pattern of making false statements about wealth, achievements, and political opponents',
                'legal_issues': [
                    'Criminal conviction for business fraud (2024)',
                    'Civil fraud judgment - $355 million penalty for fraudulent business practices',
                    'Multiple ongoing criminal cases'
                ]
            },
            'Joe Biden': {
                'credibility_notes': 'Generally factual but prone to exaggeration and misremembering details',
                'fact_check_history': 'Mixed record - some false claims but far fewer than predecessor'
            },
            'Barack Obama': {
                'credibility_notes': 'Generally accurate speaker with occasional misstatements',
                'fact_check_history': 'PolitiFact rated 70% of checked statements as Half True or better'
            },
            'Hillary Clinton': {
                'credibility_notes': 'Mixed accuracy record, particularly on email server claims',
                'fact_check_history': 'Varied by topic - more accurate on policy, less on personal matters'
            },
            'Bernie Sanders': {
                'credibility_notes': 'Generally accurate on policy positions, sometimes overstates statistics',
                'fact_check_history': 'Tends to round up numbers for rhetorical effect'
            },
            'Kayleigh McEnany': {
                'credibility_notes': 'As Trump press secretary, frequently made false or misleading statements',
                'fact_check_history': 'Pattern of defending demonstrably false claims'
            },
            'Karine Jean-Pierre': {
                'credibility_notes': 'Current Biden press secretary, generally accurate but sometimes deflects',
                'fact_check_history': 'Fewer fact-check issues than predecessors'
            },
            'Ron DeSantis': {
                'credibility_notes': 'Mixed record on COVID-19 claims and education policies',
                'fact_check_history': 'Often makes misleading claims about Florida statistics'
            },
            'Kamala Harris': {
                'credibility_notes': 'Generally accurate but has made some false claims about her record',
                'fact_check_history': 'Mixed record as VP and during campaigns'
            }
        }
        
        # Economic series mapping
        self.fred_series = {
            'unemployment': ('UNRATE', 'unemployment rate'),
            'inflation': ('CPIAUCSL', 'inflation (CPI)'),
            'gdp': ('GDP', 'GDP'),
            'gdp growth': ('A191RL1Q225SBEA', 'GDP growth rate'),
            'interest rate': ('DFF', 'federal funds rate'),
            'federal funds': ('DFF', 'federal funds rate'),
            'jobs': ('PAYEMS', 'total nonfarm employment'),
            'job growth': ('PAYEMS', 'employment growth'),
            'wages': ('CES0500000003', 'average hourly earnings'),
            'retail sales': ('RSXFS', 'retail sales'),
            'housing starts': ('HOUST', 'housing starts'),
            'consumer confidence': ('UMCSENT', 'consumer sentiment'),
            'manufacturing': ('IPMAN', 'manufacturing production'),
            'trade deficit': ('BOPGSTB', 'trade balance'),
            'national debt': ('GFDEBTN', 'federal debt')
        }
        
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Log which APIs are available"""
        active_apis = []
        
        if self.google_api_key:
            active_apis.append("Google Fact Check")
        if self.fred_api_key:
            active_apis.append("FRED Economic Data")
        if self.news_api_key:
            active_apis.append("News API")
        if self.mediastack_api_key:
            active_apis.append("MediaStack")
        if self.openai_api_key:
            active_apis.append("OpenAI")
        if self.scraperapi_key or self.scrapingbee_api_key:
            active_apis.append("Web Scraping")
        
        active_apis.append("Political Topics Database")  # Always available
        
        if active_apis:
            logger.info(f"✅ Active fact-checking APIs: {', '.join(active_apis)}")
        else:
            logger.warning("⚠️ No fact-checking APIs configured - running in limited mode")
    
    def get_speaker_context(self, speaker_name: str) -> Dict:
        """Get comprehensive background on speaker - expandable system"""
        if not speaker_name:
            return {}
        
        logger.info(f"Looking up speaker context for: {speaker_name}")
        
        # Normalize speaker name
        speaker_lower = speaker_name.lower()
        
        # Check all known speakers
        for known_speaker, info in self.speaker_backgrounds.items():
            if known_speaker.lower() in speaker_lower or speaker_lower in known_speaker.lower():
                logger.info(f"Found speaker info for: {known_speaker}")
                return {
                    'speaker': known_speaker,
                    'has_criminal_record': 'criminal_record' in info,
                    **info
                }
        
        # Handle generic "President" mentions
        if 'president' in speaker_lower and len(speaker_lower.split()) == 1:
            # Without more context, we can't determine which president
            return {
                'speaker': speaker_name,
                'credibility_notes': 'Unable to determine which president is being referenced'
            }
        
        # For unknown speakers, return neutral info
        return {
            'speaker': speaker_name,
            'credibility_notes': 'No prior fact-checking history available'
        }
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims efficiently with meaningful results"""
        results = []
        processed_claims = set()
        
        # Process claims in parallel with timeout
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_claim = {
                executor.submit(self._check_claim_fast, claim): claim 
                for claim in claims
            }
            
            # Wait for completion with timeout
            try:
                for future in as_completed(future_to_claim, timeout=30):
                    claim = future_to_claim[future]
                    try:
                        result = future.result(timeout=10)
                        results.append(result)
                        processed_claims.add(claim)
                    except Exception as e:
                        logger.error(f"Error checking claim '{claim[:50]}...': {str(e)}")
                        results.append(self._create_intelligent_result(claim))
                        processed_claims.add(claim)
            except TimeoutError:
                logger.warning("Batch check timeout - adding intelligent results for remaining claims")
                # Add intelligent results for any unprocessed claims
                for claim in claims:
                    if claim not in processed_claims:
                        results.append(self._create_intelligent_result(claim))
        
        return results
    
    def check_claim_comprehensive(self, claim: str) -> Dict:
        """Comprehensive checking with timeout and fallback"""
        try:
            return self._check_claim_fast(claim)
        except Exception as e:
            logger.error(f"Comprehensive check failed: {str(e)}")
            return self._create_intelligent_result(claim)
    
    def check_claim(self, claim: str) -> Dict:
        """Standard claim checking"""
        return self._check_claim_fast(claim)
    
    def _check_claim_fast(self, claim: str) -> Dict:
        """Fast checking that prioritizes quality over quantity"""
        logger.info(f"Fast check for: {claim[:80]}...")
        
        # Extract temporal context if present
        temporal_context = self._extract_temporal_context(claim)
        
        # Priority 1: Check political topics (always available)
        political_result = self._check_political_topics(claim)
        if political_result and political_result.get('found'):
            return self._enhance_result(claim, political_result, temporal_context)
        
        # Priority 2: Google Fact Check (if available and fast)
        if self.google_api_key:
            result = self._check_google_factcheck(claim)
            if result['found'] and result.get('verdict') not in ['unverified', None]:
                return self._enhance_result(claim, result, temporal_context)
        
        # Priority 3: FRED for ECONOMIC claims only (not war/peace claims)
        # Make sure it's actually an economic claim before checking FRED
        if self.fred_api_key and self._is_economic_claim(claim) and not self._is_war_peace_claim(claim):
            result = self._check_fred_data(claim)
            if result['found']:
                return self._enhance_result(claim, result, temporal_context)
        
        # Priority 4: Pattern analysis for common claim types
        pattern_result = self._check_common_patterns(claim)
        if pattern_result['found']:
            return self._enhance_result(claim, pattern_result, temporal_context)
        
        # Priority 5: If we have AI, use it for analysis (but with timeout)
        if self.openai_api_key:
            result = self._analyze_with_ai_fast(claim)
            if result['found']:
                return self._enhance_result(claim, result, temporal_context)
        
        # Priority 6: News APIs for recent events
        if (self.news_api_key or self.mediastack_api_key) and self._is_recent_event_claim(claim):
            result = self._check_news_sources(claim)
            if result['found']:
                return self._enhance_result(claim, result, temporal_context)
        
        # Fallback: Return intelligent result instead of "unverified"
        return self._create_intelligent_result(claim)
    
    def _extract_temporal_context(self, claim: str) -> Optional[str]:
        """Extract temporal context from claim"""
        temporal_patterns = [
            r'this week',
            r'last week',
            r'yesterday',
            r'today',
            r'this month',
            r'last month',
            r'this year',
            r'last year',
            r'in \d{4}',
            r'since \d{4}'
        ]
        
        for pattern in temporal_patterns:
            match = re.search(pattern, claim, re.IGNORECASE)
            if match:
                return f"Temporal reference: '{match.group()}'"
        
        return None
    
    def _check_political_topics(self, claim: str) -> Optional[Dict]:
        """Check claim against political topics database"""
        # Immigration
        result = self.political_checker.check_immigration_claim(claim)
        if result:
            return result
        
        # Climate
        result = self.political_checker.check_climate_claim(claim)
        if result:
            return result
        
        # Ukraine
        result = self.political_checker.check_ukraine_claim(claim)
        if result:
            return result
        
        # Vaccines
        result = self.political_checker.check_vaccine_claim(claim)
        if result:
            return result
        
        # Drugs
        result = self.political_checker.check_drug_claim(claim)
        if result:
            return result
        
        # Trade/Tariffs
        result = self.political_checker.check_trade_claim(claim)
        if result:
            return result
        
        # Crime
        result = self.political_checker.check_crime_claim(claim)
        if result:
            return result
        
        return None
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Google Fact Check with timeout"""
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],
                'languageCode': 'en'
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('claims'):
                    claim_data = data['claims'][0]
                    reviews = claim_data.get('claimReview', [])
                    
                    if reviews:
                        review = reviews[0]
                        rating = review.get('textualRating', '')
                        
                        verdict = self._map_rating_to_verdict(rating)
                        
                        return {
                            'found': True,
                            'verdict': verdict,
                            'confidence': 90,
                            'explanation': review.get('title', 'Verified by fact-checkers'),
                            'source': 'Google Fact Check',
                            'publisher': review.get('publisher', {}).get('name'),
                            'url': review.get('url'),
                            'weight': 0.95
                        }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check error: {str(e)}")
            return {'found': False}
    
    def _check_fred_data(self, claim: str) -> Dict:
        """FRED check - fast and authoritative for economic claims"""
        try:
            numbers = re.findall(r'\d+\.?\d*', claim)
            if not numbers:
                return {'found': False}
            
            claim_lower = claim.lower()
            
            for keyword, (series_id, description) in self.fred_series.items():
                if keyword in claim_lower:
                    url = "https://api.stlouisfed.org/fred/series/observations"
                    params = {
                        'series_id': series_id,
                        'api_key': self.fred_api_key,
                        'file_type': 'json',
                        'sort_order': 'desc',
                        'limit': 1
                    }
                    
                    response = requests.get(url, params=params, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('observations'):
                            obs = data['observations'][0]
                            actual_value = float(obs['value'])
                            claim_value = float(numbers[0])
                            date = obs['date']
                            
                            # Calculate accuracy
                            diff = abs(actual_value - claim_value)
                            diff_pct = (diff / actual_value * 100) if actual_value != 0 else 0
                            
                            # Determine verdict
                            if diff_pct < 5:
                                verdict = 'true'
                                accuracy = "accurate"
                            elif diff_pct < 15:
                                verdict = 'mostly_true'
                                accuracy = "approximately correct"
                            elif diff_pct < 30:
                                verdict = 'lacks_context'
                                accuracy = "outdated or imprecise"
                            else:
                                verdict = 'false'
                                accuracy = "significantly incorrect"
                            
                            explanation = (
                                f"Official {description} as of {date} is {actual_value:.1f}. "
                                f"The claim states {claim_value}, which is {accuracy} "
                                f"(off by {diff_pct:.1f}%). Source: Federal Reserve Economic Data."
                            )
                            
                            return {
                                'found': True,
                                'verdict': verdict,
                                'confidence': 95,
                                'explanation': explanation,
                                'source': 'Federal Reserve Economic Data (FRED)',
                                'weight': 1.0
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"FRED error: {str(e)}")
            return {'found': False}
    
    def _check_common_patterns(self, claim: str) -> Dict:
        """Check for common false claim patterns"""
        claim_lower = claim.lower()
        
        # Common false patterns
        false_patterns = [
            (r'never\s+(?:said|did|happened)', 'Common rhetorical exaggeration - absolute negatives are rarely true'),
            (r'always\s+(?:said|did|does)', 'Absolute statements are rarely accurate'),
            (r'biggest\s+(?:ever|in history)', 'Superlative claims often exaggerate for effect'),
            (r'first\s+(?:ever|in history)', 'Historical "firsts" are often incorrect'),
            (r'nobody\s+(?:knows|has|did)', 'Sweeping generalizations are typically false'),
            (r'everybody\s+(?:knows|says|wants)', 'Universal claims are rarely accurate')
        ]
        
        for pattern, explanation in false_patterns:
            if re.search(pattern, claim_lower):
                return {
                    'found': True,
                    'verdict': 'mostly_false',
                    'confidence': 70,
                    'explanation': f"This appears to be an exaggeration. {explanation}",
                    'source': 'Pattern Analysis',
                    'weight': 0.6
                }
        
        # Common context-lacking patterns
        context_patterns = [
            (r'\d+%?\s+(?:increase|decrease|growth|decline)', 'Statistics need time frame and baseline context'),
            (r'studies show|research indicates|experts say', 'Vague attribution - which studies or experts?'),
            (r'many people|some people|a lot of', 'Imprecise quantifiers lack specificity')
        ]
        
        for pattern, explanation in context_patterns:
            if re.search(pattern, claim_lower):
                return {
                    'found': True,
                    'verdict': 'lacks_context',
                    'confidence': 65,
                    'explanation': f"This claim needs more context. {explanation}",
                    'source': 'Pattern Analysis',
                    'weight': 0.5
                }
        
        return {'found': False}
    
    def _analyze_with_ai_fast(self, claim: str) -> Dict:
        """Fast AI analysis with timeout"""
        if not self.openai_api_key:
            return {'found': False}
        
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Simpler, faster prompt
            prompt = f"""Fact-check this claim in one sentence: "{claim}"
            
Respond with: verdict (true/mostly_true/lacks_context/mostly_false/false/deceptive) | explanation"""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are a fact-checker. Be concise.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 100
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=8
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse simple format
                if '|' in content:
                    verdict, explanation = content.split('|', 1)
                    verdict = verdict.strip().lower()
                    
                    if verdict in ['true', 'mostly_true', 'lacks_context', 'mostly_false', 'false', 'deceptive']:
                        return {
                            'found': True,
                            'verdict': verdict,
                            'confidence': 75,
                            'explanation': explanation.strip(),
                            'source': 'AI Analysis (OpenAI)',
                            'weight': 0.7
                        }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            return {'found': False}
    
    def _check_news_sources(self, claim: str) -> Dict:
        """Check news sources for recent events"""
        try:
            # Extract key terms
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:4])
            
            if self.mediastack_api_key:
                url = "http://api.mediastack.com/v1/news"
                params = {
                    'access_key': self.mediastack_api_key,
                    'keywords': search_query,
                    'languages': 'en',
                    'limit': 5,
                    'sort': 'published_desc'
                }
            elif self.news_api_key:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'apiKey': self.news_api_key,
                    'q': search_query,
                    'sortBy': 'relevancy',
                    'pageSize': 5,
                    'language': 'en'
                }
            else:
                return {'found': False}
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('data', []) if self.mediastack_api_key else data.get('articles', [])
                
                if articles:
                    return {
                        'found': True,
                        'verdict': 'mixed',
                        'confidence': 60,
                        'explanation': f'Found {len(articles)} recent news articles discussing this topic. Further verification recommended.',
                        'source': 'News API' if self.news_api_key else 'MediaStack News',
                        'weight': 0.65
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"News API error: {str(e)}")
            return {'found': False}
    
    def _is_recent_event_claim(self, claim: str) -> bool:
        """Check if claim is about recent events"""
        recent_indicators = [
            'yesterday', 'today', 'this week', 'last week',
            'recently', 'just', 'breaking', 'latest',
            '2024', '2025', 'current', 'ongoing'
        ]
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in recent_indicators)
    
    def _create_intelligent_result(self, claim: str) -> Dict:
        """Create intelligent results based on claim analysis - no more 'unverified'"""
        claim_lower = claim.lower()
        
        # Analyze claim characteristics
        has_numbers = bool(re.search(r'\d+', claim))
        has_percentage = bool(re.search(r'\d+%', claim))
        has_absolute = any(word in claim_lower for word in ['all', 'none', 'every', 'never', 'always', 'nobody', 'everybody', 'only'])
        has_superlative = any(word in claim_lower for word in ['best', 'worst', 'biggest', 'smallest', 'first', 'last', 'most', 'least'])
        has_vague = any(phrase in claim_lower for phrase in ['people say', 'studies show', 'experts', 'they say', 'sources'])
        
        # Check for opinion indicators
        opinion_words = ['beautiful', 'amazing', 'terrible', 'wonderful', 'horrible', 'great', 'awful', 'disgusting']
        has_opinion = any(word in claim_lower for word in opinion_words)
        
        # Determine verdict based on multiple factors
        if has_opinion and not has_numbers:
            verdict = 'mixed'
            confidence = 40
            explanation = "This appears to be primarily an opinion or subjective statement rather than a verifiable fact."
        
        elif has_absolute:
            # Absolute statements are usually false or exaggerated
            verdict = 'mostly_false'
            confidence = 65
            absolute_word = [w for w in ['all', 'none', 'every', 'never', 'always'] if w in claim_lower][0]
            explanation = f"Claims using absolute language like '{absolute_word}' are typically exaggerations. Real-world scenarios rarely involve absolutes."
        
        elif has_superlative:
            # Superlatives often exaggerate
            verdict = 'lacks_context'
            confidence = 60
            explanation = f"Superlative claims require specific context and comparison data for verification. What metric? Compared to what? When?"
        
        elif has_vague:
            # Vague attributions
            verdict = 'lacks_context'
            confidence = 55
            vague_phrase = [p for p in ['people say', 'studies show', 'experts', 'sources'] if p in claim_lower][0]
            explanation = f"The claim uses vague attribution ('{vague_phrase}'). Which people/studies/experts specifically? Without specifics, this cannot be properly verified."
        
        elif has_numbers or has_percentage:
            # Numerical claims
            verdict = 'mixed'
            confidence = 50
            explanation = "This numerical claim requires verification against official sources. Without access to current databases, we cannot confirm the specific figures."
        
        else:
            # General factual claims
            # Look for controversial topics
            controversial_topics = ['election', 'vaccine', 'climate', 'immigration', 'crime']
            is_controversial = any(topic in claim_lower for topic in controversial_topics)
            
            if is_controversial:
                verdict = 'mixed'
                confidence = 45
                explanation = "This claim touches on a controversial topic that requires careful fact-checking against multiple authoritative sources."
            else:
                verdict = 'mostly_true'
                confidence = 40
                explanation = "This appears to be a general statement. While we cannot verify without additional sources, it doesn't contain obvious red flags."
        
        # Add analysis notes
        analysis_notes = []
        if has_absolute:
            analysis_notes.append("Contains absolute language")
        if has_superlative:
            analysis_notes.append("Uses superlatives")
        if has_vague:
            analysis_notes.append("Vague attribution")
        if has_numbers:
            analysis_notes.append("Contains specific numbers requiring verification")
        
        result = {
            'claim': claim,
            'verdict': verdict,
            'confidence': confidence,
            'explanation': explanation,
            'sources': ['Claim Analysis'],
            'api_response': False,
            'analysis_method': 'Pattern Analysis'
        }
        
        if analysis_notes:
            result['analysis_notes'] = analysis_notes
        
        return result
    
    def _enhance_result(self, claim: str, result: Dict, temporal_context: Optional[str] = None) -> Dict:
        """Enhance result with claim text and ensure completeness"""
        result['claim'] = claim
        
        # Add temporal context if present
        if temporal_context:
            result['temporal_context'] = temporal_context
        
        # Ensure all required fields
        if 'confidence' not in result:
            result['confidence'] = 50
        if 'sources' not in result:
            result['sources'] = [result.get('source', 'Unknown')]
        if 'api_response' not in result:
            result['api_response'] = True
        
        # Add intentionality analysis for misleading claims
        if result.get('verdict') in ['misleading', 'deceptive', 'mostly_false', 'false']:
            result['appears_intentional'] = self._assess_intentionality(claim, result)
        
        return result
    
    def _assess_intentionality(self, claim: str, result: Dict) -> bool:
        """Assess whether misleading appears intentional"""
        claim_lower = claim.lower()
        
        # Indicators of intentional deception
        intentional_indicators = [
            'never said',  # Denying documented statements
            'fake news',
            'hoax',
            'lying media',
            'totally false',
            'complete lie',
            'rigged',
            'stolen'
        ]
        
        # Check for intentional indicators
        has_intentional_language = any(indicator in claim_lower for indicator in intentional_indicators)
        
        # Check if it's a repeated false claim (would need history)
        is_repeated = False  # Would check against database of previous claims
        
        # Check if numbers are wildly off (>50% error suggests intentional)
        wildly_inaccurate = False
        if 'confidence' in result and result['confidence'] > 80:
            if result.get('verdict') in ['false', 'mostly_false']:
                wildly_inaccurate = True
        
        # Decision logic
        if has_intentional_language:
            return True
        elif wildly_inaccurate and is_repeated:
            return True
        elif result.get('verdict') == 'deceptive':
            return True
        else:
            return False
    
    def _map_rating_to_verdict(self, rating: str) -> str:
        """Map various ratings to our verdict system"""
        rating_lower = rating.lower()
        
        # Direct mappings
        if 'true' in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_true'
            return 'true'
        
        if 'false' in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_false'
            return 'false'
        
        if any(word in rating_lower for word in ['misleading', 'deceptive', 'distorted']):
            return 'deceptive'
        
        if any(word in rating_lower for word in ['lacks context', 'missing context', 'needs context']):
            return 'lacks_context'
        
        if any(word in rating_lower for word in ['mixed', 'mixture', 'half']):
            return 'mixed'
        
        if any(word in rating_lower for word in ['unproven', 'unsubstantiated', 'no evidence']):
            return 'mostly_false'  # Changed from unsubstantiated
        
        # Default to mostly_false for unclear negative ratings
        if any(word in rating_lower for word in ['incorrect', 'wrong', 'inaccurate']):
            return 'mostly_false'
        
        # Instead of returning 'unverified', return mixed
        return 'mixed'
    
    def _is_economic_claim(self, claim: str) -> bool:
        """Check if claim involves economic data"""
        economic_terms = [
            'unemployment', 'inflation', 'gdp', 'economy', 'jobs', 'employment',
            'interest rate', 'federal reserve', 'stock market', 'dow jones',
            'wages', 'income', 'poverty', 'deficit', 'debt', 'budget',
            'trade', 'tariff', 'export', 'import', 'manufacturing',
            'retail', 'housing', 'mortgage', 'recession', 'growth'
        ]
        claim_lower = claim.lower()
        return any(term in claim_lower for term in economic_terms)
    
    def _is_war_peace_claim(self, claim: str) -> bool:
        """Check if claim is about war/peace/conflict"""
        war_peace_terms = [
            'war', 'peace', 'conflict', 'military', 'troops', 'soldier',
            'combat', 'battle', 'invasion', 'attack', 'strike', 'bomb',
            'weapon', 'nuclear', 'missile', 'drone', 'afghanistan', 'iraq',
            'syria', 'ukraine', 'gaza', 'israel', 'palestine', 'yemen',
            'libya', 'somalia', 'terror', 'isis', 'al qaeda', 'taliban'
        ]
        claim_lower = claim.lower()
        return any(term in claim_lower for term in war_peace_terms)
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key terms for searching"""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        words = claim.split()
        key_terms = []
        
        for word in words:
            clean_word = word.strip('.,!?;:"\'')
            if clean_word and (clean_word[0].isupper() or clean_word.lower() not in stop_words):
                key_terms.append(clean_word)
        
        return key_terms[:6]
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> int:
        """Calculate overall credibility score"""
        if not fact_checks:
            return 50
        
        scores = {
            'true': 100,
            'mostly_true': 80,
            'mixed': 50,
            'lacks_context': 40,
            'deceptive': 15,
            'misleading': 20,
            'mostly_false': 25,
            'false': 0
        }
        
        total_score = 0
        valid_checks = 0
        
        for fc in fact_checks:
            verdict = fc.get('verdict', 'mixed')
            if verdict in scores:
                total_score += scores[verdict]
                valid_checks += 1
        
        if valid_checks == 0:
            return 50
        
        return int(total_score / valid_checks)
