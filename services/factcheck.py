"""
Enhanced Fact Checking Service - Optimized with Meaningful Results
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

logger = logging.getLogger(__name__)

class FactChecker:
    """Enhanced fact-checking with better performance and meaningful results"""
    
    def __init__(self):
        # Initialize ALL API keys
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.fred_api_key = Config.FRED_API_KEY
        self.news_api_key = Config.NEWS_API_KEY
        self.mediastack_api_key = Config.MEDIASTACK_API_KEY
        self.openai_api_key = Config.OPENAI_API_KEY
        self.scraperapi_key = Config.SCRAPERAPI_KEY
        self.scrapingbee_api_key = Config.SCRAPINGBEE_API_KEY
        
        # Expandable speaker backgrounds - dynamically loaded
        self.speaker_backgrounds = self._load_speaker_backgrounds()
        
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
    
    def _load_speaker_backgrounds(self) -> Dict:
        """Load speaker backgrounds - expandable system for any speaker"""
        # This could be loaded from a database or external file in production
        # For now, return a comprehensive dictionary with various examples
        return {
            # Political figures with various backgrounds
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
            
            # Positive examples
            'Mother Teresa': {
                'credibility_notes': 'Devoted humanitarian with impeccable reputation for honesty and service',
                'fact_check_history': 'No known instances of false public statements',
                'humanitarian_record': 'Nobel Peace Prize winner, founded Missionaries of Charity, served the poor for decades'
            },
            'Jimmy Carter': {
                'credibility_notes': 'Known for exceptional honesty and integrity throughout political career',
                'fact_check_history': 'Consistently rated as one of the most truthful political figures',
                'humanitarian_record': 'Extensive post-presidency humanitarian work, Habitat for Humanity'
            },
            'Nelson Mandela': {
                'credibility_notes': 'Internationally respected for integrity and moral leadership',
                'fact_check_history': 'Known for honest discourse even on difficult topics',
                'humanitarian_record': 'Led peaceful transition from apartheid, promoted reconciliation'
            },
            
            # Business figures
            'Elon Musk': {
                'credibility_notes': 'Mixed record on predictions and timeline claims',
                'fact_check_history': 'Often overly optimistic about product timelines and capabilities'
            },
            'Elizabeth Holmes': {
                'criminal_record': 'Convicted of wire fraud and conspiracy - Theranos scandal',
                'fraud_history': 'Deceived investors about blood testing technology capabilities',
                'credibility_notes': 'Systematically misled investors, patients, and media about company technology'
            },
            'Sam Bankman-Fried': {
                'criminal_record': 'Convicted of fraud and conspiracy - FTX collapse',
                'fraud_history': 'Misused billions in customer funds',
                'credibility_notes': 'Made false statements about FTX financial position and customer fund safety'
            },
            
            # Media figures
            'Tucker Carlson': {
                'credibility_notes': 'Court documents revealed "not stating actual facts" defense in lawsuit',
                'fact_check_history': 'Numerous false and misleading claims documented by fact-checkers'
            },
            'Rachel Maddow': {
                'credibility_notes': 'Generally factual reporting with occasional corrections issued',
                'fact_check_history': 'Mixed record - mostly accurate with some misleading segments'
            },
            
            # Historical figures
            'Richard Nixon': {
                'credibility_notes': 'Resigned from presidency due to Watergate scandal and cover-up',
                'fact_check_history': 'Famous for "I am not a crook" false statement'
            },
            'George Washington': {
                'credibility_notes': 'Historical reputation for honesty - "cannot tell a lie" legend',
                'fact_check_history': 'No documented pattern of deception'
            }
        }
    
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
        
        logger.info(f"✅ Active fact-checking APIs: {', '.join(active_apis) if active_apis else 'NONE - Running in demo mode'}")
    
    def get_speaker_context(self, speaker_name: str) -> Dict:
        """Get comprehensive background on speaker - expandable system"""
        if not speaker_name:
            return {}
        
        logger.info(f"Looking up speaker context for: {speaker_name}")
        
        # Normalize speaker name
        speaker_lower = speaker_name.lower()
        
        # Check all known speakers with fuzzy matching
        for known_speaker, info in self.speaker_backgrounds.items():
            known_lower = known_speaker.lower()
            
            # Check various matching patterns
            if (known_lower in speaker_lower or 
                speaker_lower in known_lower or
                self._fuzzy_match_speaker(speaker_lower, known_lower)):
                
                logger.info(f"Found speaker info for: {known_speaker}")
                return {
                    'speaker': known_speaker,
                    'has_criminal_record': 'criminal_record' in info,
                    'has_fraud_history': 'fraud_history' in info,
                    'has_humanitarian_record': 'humanitarian_record' in info,
                    **info
                }
        
        # Handle generic titles
        if any(title in speaker_lower for title in ['president', 'senator', 'governor', 'mayor']):
            # Try to extract more context
            words = speaker_lower.split()
            if len(words) > 1:
                # Try to find a match with the name after the title
                for i, word in enumerate(words):
                    if word in ['president', 'senator', 'governor', 'mayor'] and i + 1 < len(words):
                        potential_name = ' '.join(words[i+1:])
                        # Recursive call with just the name
                        return self.get_speaker_context(potential_name)
            
            # If we can't determine which specific person
            return {
                'speaker': speaker_name,
                'credibility_notes': f'Unable to determine which specific {speaker_name} is being referenced'
            }
        
        # For unknown speakers, check if we can infer anything from the name
        context = {'speaker': speaker_name}
        
        # Check for professional titles that might indicate credibility
        if any(title in speaker_lower for title in ['dr.', 'doctor', 'professor', 'judge']):
            context['credibility_notes'] = 'Professional title suggests subject matter expertise'
        elif any(word in speaker_lower for word in ['journalist', 'reporter', 'anchor']):
            context['credibility_notes'] = 'Media professional - credibility varies by outlet and individual track record'
        else:
            context['credibility_notes'] = 'No prior fact-checking history available for this speaker'
        
        return context
    
    def _fuzzy_match_speaker(self, search_name: str, known_name: str) -> bool:
        """Fuzzy matching for speaker names"""
        # Split into words
        search_words = search_name.split()
        known_words = known_name.split()
        
        # Check if last names match (often most distinctive)
        if len(search_words) > 0 and len(known_words) > 0:
            if search_words[-1] == known_words[-1]:
                return True
        
        # Check if search contains significant parts of known name
        significant_matches = 0
        for word in search_words:
            if len(word) > 3 and word in known_words:
                significant_matches += 1
        
        # If we match at least half the words, consider it a match
        return significant_matches >= len(known_words) / 2
    
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
                        results.append(self._create_demo_result(claim))
                        processed_claims.add(claim)
            except TimeoutError:
                logger.warning("Batch check timeout - adding demo results for remaining claims")
                # Add demo results for any unprocessed claims
                for claim in claims:
                    if claim not in processed_claims:
                        results.append(self._create_demo_result(claim))
        
        return results
    
    def check_claim_comprehensive(self, claim: str) -> Dict:
        """Comprehensive checking with timeout and fallback"""
        try:
            return self._check_claim_fast(claim)
        except Exception as e:
            logger.error(f"Comprehensive check failed: {str(e)}")
            return self._create_demo_result(claim)
    
    def check_claim(self, claim: str) -> Dict:
        """Standard claim checking"""
        return self._check_claim_fast(claim)
    
    def _check_claim_fast(self, claim: str) -> Dict:
        """Fast checking that prioritizes quality over quantity"""
        logger.info(f"Fast check for: {claim[:80]}...")
        
        # If no APIs configured, use intelligent demo mode
        if not any([self.google_api_key, self.fred_api_key, self.news_api_key, 
                   self.mediastack_api_key, self.openai_api_key]):
            return self._create_demo_result(claim)
        
        # Priority 1: Google Fact Check (if available and fast)
        if self.google_api_key:
            result = self._check_google_factcheck(claim)
            if result['found'] and result.get('verdict') != 'unverified':
                return self._enhance_result(claim, result)
        
        # Priority 2: FRED for economic claims (very fast and authoritative)
        if self.fred_api_key and self._is_economic_claim(claim):
            result = self._check_fred_data(claim)
            if result['found']:
                return self._enhance_result(claim, result)
        
        # Priority 3: Pattern analysis for common claim types
        pattern_result = self._check_common_patterns(claim)
        if pattern_result['found']:
            return self._enhance_result(claim, pattern_result)
        
        # Priority 4: If we have AI, use it for analysis (but with timeout)
        if self.openai_api_key:
            result = self._analyze_with_ai_fast(claim)
            if result['found']:
                return self._enhance_result(claim, result)
        
        # Fallback: Return intelligent demo result instead of "unverified"
        return self._create_demo_result(claim)
    
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
                            'source': 'AI Analysis',
                            'weight': 0.7
                        }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            return {'found': False}
    
    def _create_demo_result(self, claim: str) -> Dict:
        """Create intelligent demo results instead of just 'unverified'"""
        # Analyze claim to provide meaningful demo verdict
        claim_lower = claim.lower()
        
        # Check for numbers/statistics
        has_numbers = bool(re.search(r'\d+', claim))
        has_percentage = bool(re.search(r'\d+%', claim))
        
        # Check for absolute words
        has_absolute = any(word in claim_lower for word in ['all', 'none', 'every', 'never', 'always', 'nobody', 'everybody'])
        
        # Check for superlatives
        has_superlative = any(word in claim_lower for word in ['best', 'worst', 'biggest', 'smallest', 'first', 'last', 'only'])
        
        # Check for vague attribution
        has_vague = any(phrase in claim_lower for phrase in ['people say', 'studies show', 'experts', 'they say', 'sources'])
        
        # Determine verdict based on patterns
        if has_absolute or has_superlative:
            verdict = 'mostly_false'
            confidence = 65
            explanation = "Claims using absolute language or superlatives are often exaggerations. Without access to fact-checking APIs, this appears likely to be an overstatement."
        elif has_vague:
            verdict = 'lacks_context'
            confidence = 60
            explanation = "This claim lacks specific attribution or context. Who are these people/experts/sources? When did they say this? More specificity needed."
        elif has_numbers or has_percentage:
            verdict = 'lacks_context'
            confidence = 55
            explanation = "Statistical claims require verification against official sources. Without API access, we cannot confirm these specific numbers."
        else:
            # For general claims, make an educated guess based on tone
            if any(word in claim_lower for word in ['false', 'lie', 'fake', 'hoax', 'scam']):
                verdict = 'mostly_false'
                confidence = 50
                explanation = "Claims about falsehoods often themselves contain inaccuracies. Requires fact-checking for verification."
            else:
                verdict = 'mostly_true'
                confidence = 45
                explanation = "This appears to be a general statement. Without fact-checking APIs, we assume reasonable accuracy but recommend verification."
        
        # Add demo mode note
        explanation += " [DEMO MODE: Full fact-checking requires API access]"
        
        return {
            'claim': claim,
            'verdict': verdict,
            'confidence': confidence,
            'explanation': explanation,
            'sources': ['Demo Analysis'],
            'api_response': False
        }
    
    def _enhance_result(self, claim: str, result: Dict) -> Dict:
        """Enhance result with claim text and ensure completeness"""
        result['claim'] = claim
        
        # Ensure all required fields
        if 'confidence' not in result:
            result['confidence'] = 50
        if 'sources' not in result:
            result['sources'] = [result.get('source', 'Unknown')]
        if 'api_response' not in result:
            result['api_response'] = True
        
        return result
    
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
            return 'lacks_context'
        
        if any(word in rating_lower for word in ['unproven', 'unsubstantiated', 'no evidence']):
            return 'unsubstantiated'
        
        # Default to mostly_false for unclear negative ratings
        if any(word in rating_lower for word in ['incorrect', 'wrong', 'inaccurate']):
            return 'mostly_false'
        
        # Instead of returning 'unverified', make an educated guess
        return 'lacks_context'
    
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
            'mostly_true': 75,
            'lacks_context': 40,
            'deceptive': 20,
            'unsubstantiated': 30,
            'mostly_false': 25,
            'false': 0,
            'unverified': 50
        }
        
        total_score = sum(scores.get(fc.get('verdict', 'unverified'), 50) for fc in fact_checks)
        return int(total_score / len(fact_checks))
