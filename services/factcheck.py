"""
Enhanced Fact Checking Service - Main Module
Coordinates fact-checking using multiple sources with REAL API integration
"""
import os
import re
import time
import json
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Main fact-checking coordinator with real API integration"""
    
    def __init__(self):
        # Initialize with actual API keys from Config
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.fred_api_key = Config.FRED_API_KEY
        self.news_api_key = Config.NEWS_API_KEY
        self.mediastack_api_key = Config.MEDIASTACK_API_KEY
        self.openai_api_key = Config.OPENAI_API_KEY
        
        # Validate configuration
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate that the fact checker is properly configured"""
        active_apis = []
        
        if self.google_api_key:
            active_apis.append("Google Fact Check")
        if self.fred_api_key:
            active_apis.append("FRED Economic Data")
        if self.news_api_key:
            active_apis.append("News API")
        if self.mediastack_api_key:
            active_apis.append("MediaStack News")
        if self.openai_api_key:
            active_apis.append("OpenAI Analysis")
        
        if active_apis:
            logger.info(f"✅ Fact checker initialized with APIs: {', '.join(active_apis)}")
        else:
            logger.warning("⚠️ No fact-checking APIs configured - using demo mode")
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims using real APIs"""
        results = []
        
        # If no API keys configured, return demo results
        if not any([self.google_api_key, self.fred_api_key, self.news_api_key]):
            logger.warning("No API keys configured - returning demo results")
            return self._generate_demo_results(claims)
        
        # Use real API checking
        for i, claim in enumerate(claims):
            try:
                logger.info(f"Checking claim {i+1}/{len(claims)}: {claim[:80]}...")
                result = self.check_claim(claim)
                results.append(result)
                
                # Rate limiting
                if i < len(claims) - 1:
                    time.sleep(Config.FACT_CHECK_RATE_LIMIT_DELAY)
                    
            except Exception as e:
                logger.error(f"Error checking claim: {str(e)}")
                results.append(self._create_error_result(claim))
        
        return results
    
    def check_claim(self, claim: str) -> Dict:
        """Check a single claim using multiple real APIs"""
        check_results = []
        
        # 1. Try Google Fact Check API first (highest authority)
        if self.google_api_key:
            google_result = self._check_google_factcheck(claim)
            if google_result['found']:
                check_results.append(google_result)
                # If Google has a strong verdict, we can return early
                if google_result.get('confidence', 0) >= 85:
                    return self._format_result(claim, google_result)
        
        # 2. Check economic claims against FRED
        if self.fred_api_key and self._is_economic_claim(claim):
            fred_result = self._check_fred_data(claim)
            if fred_result['found']:
                check_results.append(fred_result)
        
        # 3. Check news sources
        if self.news_api_key or self.mediastack_api_key:
            news_result = self._check_news_sources(claim)
            if news_result['found']:
                check_results.append(news_result)
        
        # 4. Use OpenAI for complex analysis if available
        if self.openai_api_key and len(check_results) == 0:
            ai_result = self._check_with_openai(claim)
            if ai_result['found']:
                check_results.append(ai_result)
        
        # Synthesize results from multiple sources
        if check_results:
            return self._synthesize_results(claim, check_results)
        else:
            return self._create_unverified_response(claim, "No verification sources found")
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Real Google Fact Check API implementation"""
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],  # API has query length limit
                'languageCode': 'en'
            }
            
            logger.info(f"Calling Google Fact Check API for: {claim[:80]}...")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('claims'):
                    # Process the first matching claim
                    claim_data = data['claims'][0]
                    claim_review = claim_data.get('claimReview', [{}])[0]
                    
                    # Extract verdict and details
                    rating = claim_review.get('textualRating', 'unverified')
                    verdict = self._map_google_rating(rating)
                    publisher = claim_review.get('publisher', {}).get('name', 'Unknown')
                    
                    logger.info(f"Google Fact Check found: {rating} from {publisher}")
                    
                    return {
                        'found': True,
                        'verdict': verdict,
                        'confidence': 85,
                        'explanation': claim_review.get('title', 'Verified by fact-checkers'),
                        'source': f'Google Fact Check ({publisher})',
                        'publisher': publisher,
                        'url': claim_review.get('url', ''),
                        'weight': 0.9
                    }
                else:
                    logger.info("No results from Google Fact Check")
            else:
                logger.error(f"Google API error: {response.status_code}")
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {str(e)}")
            return {'found': False}
    
    def _check_fred_data(self, claim: str) -> Dict:
        """Check economic claims against FRED data"""
        try:
            # Extract numbers from claim
            numbers = re.findall(r'\d+\.?\d*', claim)
            if not numbers:
                return {'found': False}
            
            claim_lower = claim.lower()
            
            # Map claim keywords to FRED series IDs
            series_map = {
                'unemployment': 'UNRATE',
                'inflation': 'CPIAUCSL',
                'gdp': 'GDP',
                'interest rate': 'DFF',
                'federal funds': 'DFF',
                'jobs': 'PAYEMS',
                'employment': 'PAYEMS',
                'retail sales': 'RSXFS',
                'housing starts': 'HOUST',
                'consumer confidence': 'UMCSENT'
            }
            
            for keyword, series_id in series_map.items():
                if keyword in claim_lower:
                    url = f"https://api.stlouisfed.org/fred/series/observations"
                    params = {
                        'series_id': series_id,
                        'api_key': self.fred_api_key,
                        'file_type': 'json',
                        'sort_order': 'desc',
                        'limit': 1
                    }
                    
                    logger.info(f"Checking FRED data for {keyword}...")
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('observations'):
                            latest_value = float(data['observations'][0]['value'])
                            claim_value = float(numbers[0])
                            date = data['observations'][0]['date']
                            
                            # Compare values
                            diff_pct = abs(latest_value - claim_value) / latest_value * 100
                            
                            if diff_pct < 5:
                                verdict = 'true'
                                confidence = 90
                            elif diff_pct < 10:
                                verdict = 'mostly_true'
                                confidence = 80
                            elif diff_pct < 20:
                                verdict = 'mixed'
                                confidence = 70
                            else:
                                verdict = 'false'
                                confidence = 85
                            
                            explanation = f"Federal Reserve data from {date} shows {keyword} at {latest_value}"
                            if claim_value != latest_value:
                                explanation += f" (claim states {claim_value}, difference of {diff_pct:.1f}%)"
                            
                            logger.info(f"FRED verdict: {verdict} (diff: {diff_pct:.1f}%)")
                            
                            return {
                                'found': True,
                                'verdict': verdict,
                                'confidence': confidence,
                                'explanation': explanation,
                                'source': 'Federal Reserve Economic Data (FRED)',
                                'weight': 0.95
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"FRED API error: {str(e)}")
            return {'found': False}
    
    def _check_news_sources(self, claim: str) -> Dict:
        """Check news sources for claim verification"""
        # Try MediaStack first, then News API
        if self.mediastack_api_key:
            return self._check_mediastack(claim)
        elif self.news_api_key:
            return self._check_newsapi(claim)
        return {'found': False}
    
    def _check_newsapi(self, claim: str) -> Dict:
        """Check News API for relevant articles"""
        try:
            # Extract key terms
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:3])
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.news_api_key,
                'q': search_query,
                'sortBy': 'relevancy',
                'pageSize': 5,
                'language': 'en'
            }
            
            logger.info(f"Checking News API for: {search_query}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('articles'):
                    article_count = len(data['articles'])
                    sources = [art.get('source', {}).get('name', 'Unknown') for art in data['articles'][:3]]
                    
                    logger.info(f"Found {article_count} news articles")
                    
                    return {
                        'found': True,
                        'verdict': 'mixed',
                        'confidence': 60,
                        'explanation': f'Found {article_count} news articles discussing this topic from: {", ".join(sources)}',
                        'source': 'News API',
                        'weight': 0.6
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"News API error: {str(e)}")
            return {'found': False}
    
    def _check_mediastack(self, claim: str) -> Dict:
        """Check MediaStack news API"""
        try:
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:4])
            
            url = "http://api.mediastack.com/v1/news"
            params = {
                'access_key': self.mediastack_api_key,
                'keywords': search_query,
                'languages': 'en',
                'limit': 10,
                'sort': 'published_desc'
            }
            
            logger.info(f"Checking MediaStack for: {search_query}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    article_count = len(data['data'])
                    sources = [art.get('source', 'Unknown') for art in data['data'][:3]]
                    
                    return {
                        'found': True,
                        'verdict': 'mixed',
                        'confidence': 60,
                        'explanation': f'Found {article_count} recent news articles from: {", ".join(sources)}',
                        'source': 'MediaStack News',
                        'weight': 0.6
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"MediaStack API error: {str(e)}")
            return {'found': False}
    
    def _check_with_openai(self, claim: str) -> Dict:
        """Use OpenAI for claim analysis"""
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""Analyze this claim for factual accuracy: "{claim}"
            
            Provide:
            1. Verdict: true, mostly_true, mixed, lacks_context, deceptive, mostly_false, false, or unverified
            2. Confidence: 0-100
            3. Brief explanation (max 100 words)
            
            Format as JSON: {{"verdict": "", "confidence": 0, "explanation": ""}}"""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are a professional fact-checker.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 200
            }
            
            logger.info("Checking with OpenAI...")
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('choices'):
                    content = result['choices'][0]['message']['content']
                    # Parse JSON response
                    analysis = json.loads(content)
                    
                    return {
                        'found': True,
                        'verdict': analysis.get('verdict', 'mixed'),
                        'confidence': analysis.get('confidence', 70),
                        'explanation': analysis.get('explanation', 'AI analysis completed'),
                        'source': 'OpenAI Analysis',
                        'weight': 0.7
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {'found': False}
    
    def _synthesize_results(self, claim: str, check_results: List[Dict]) -> Dict:
        """Combine multiple check results into final verdict"""
        if not check_results:
            return self._create_unverified_response(claim, "No sources available")
        
        # If only one result, use it directly
        if len(check_results) == 1:
            return self._format_result(claim, check_results[0])
        
        # Weight and combine multiple results
        weighted_scores = []
        all_sources = []
        all_explanations = []
        highest_confidence = 0
        
        verdict_scores = {
            'true': 1.0,
            'mostly_true': 0.75,
            'mixed': 0.5,
            'lacks_context': 0.4,
            'deceptive': 0.3,
            'mostly_false': 0.25,
            'false': 0.0,
            'unverified': 0.5
        }
        
        for result in check_results:
            weight = result.get('weight', 0.5)
            confidence = result.get('confidence', 50)
            verdict = result.get('verdict', 'unverified')
            score = verdict_scores.get(verdict, 0.5)
            
            weighted_scores.append((score, weight, confidence))
            all_sources.append(result.get('source', 'Unknown'))
            all_explanations.append(result.get('explanation', ''))
            highest_confidence = max(highest_confidence, confidence)
        
        # Calculate weighted average
        total_weight = sum(w for _, w, _ in weighted_scores)
        weighted_sum = sum(s * w for s, w, _ in weighted_scores)
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        # Convert score back to verdict
        if final_score >= 0.85:
            final_verdict = 'true'
        elif final_score >= 0.65:
            final_verdict = 'mostly_true'
        elif final_score >= 0.45:
            final_verdict = 'mixed'
        elif final_score >= 0.25:
            final_verdict = 'mostly_false'
        else:
            final_verdict = 'false'
        
        # Combine explanations
        combined_explanation = f"Verified by {len(check_results)} sources. "
        combined_explanation += " ".join(all_explanations[:2])
        
        return {
            'claim': claim,
            'verdict': final_verdict,
            'confidence': highest_confidence,
            'explanation': combined_explanation,
            'sources': all_sources,
            'api_response': True
        }
    
    def _format_result(self, claim: str, result: Dict) -> Dict:
        """Format a single result for return"""
        return {
            'claim': claim,
            'verdict': result.get('verdict', 'unverified'),
            'confidence': result.get('confidence', 0),
            'explanation': result.get('explanation', 'No explanation available'),
            'sources': [result.get('source', 'Unknown')],
            'publisher': result.get('publisher'),
            'url': result.get('url', ''),
            'api_response': True
        }
    
    def _map_google_rating(self, rating: str) -> str:
        """Map Google's rating to our verdict system"""
        rating_lower = rating.lower()
        
        mapping = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'half true': 'mixed',
            'mixture': 'mixed',
            'mostly false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'misleading': 'deceptive',
            'lacks context': 'lacks_context',
            'unproven': 'unverified',
            'outdated': 'mostly_false',
            'scam': 'false'
        }
        
        for key, verdict in mapping.items():
            if key in rating_lower:
                return verdict
        
        return 'unverified'
    
    def _is_economic_claim(self, claim: str) -> bool:
        """Check if claim is about economic data"""
        economic_keywords = [
            'unemployment', 'inflation', 'gdp', 'economy', 'jobs',
            'interest rate', 'federal reserve', 'stock market',
            'wages', 'income', 'poverty', 'deficit', 'debt',
            'trade', 'tariff', 'export', 'import'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in economic_keywords)
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key search terms from claim"""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be'}
        
        words = claim.split()
        key_terms = []
        
        # Keep proper nouns and important words
        for word in words:
            clean_word = word.strip('.,!?;:"')
            if clean_word and (clean_word[0].isupper() or clean_word.lower() not in stop_words):
                key_terms.append(clean_word)
        
        return key_terms[:5]
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> int:
        """Calculate overall credibility score"""
        if not fact_checks:
            return 50
        
        scores = {
            'true': 100,
            'mostly_true': 75,
            'mixed': 50,
            'lacks_context': 40,
            'deceptive': 25,
            'mostly_false': 25,
            'false': 0,
            'unverified': 50
        }
        
        total_score = sum(scores.get(fc.get('verdict', 'unverified'), 50) for fc in fact_checks)
        return int(total_score / len(fact_checks))
    
    def _create_unverified_response(self, claim: str, reason: str) -> Dict:
        """Create response for unverified claims"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': f'❓ UNVERIFIED: {reason}',
            'sources': [],
            'api_response': False
        }
    
    def _create_error_result(self, claim: str) -> Dict:
        """Create result for errors"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'Error during fact-checking process',
            'sources': ['Error'],
            'api_response': False
        }
    
    def _generate_demo_results(self, claims: List[str]) -> List[Dict]:
        """Generate demo results only when no APIs are configured"""
        demo_verdicts = ['true', 'mostly_true', 'mixed', 'false', 'unverified']
        results = []
        
        for i, claim in enumerate(claims):
            verdict = demo_verdicts[i % len(demo_verdicts)]
            results.append({
                'claim': claim,
                'verdict': verdict,
                'confidence': 65 + (i % 30),
                'explanation': f"[DEMO MODE - Configure API keys for real results] This would be checked against real sources",
                'sources': ['Demo Mode'],
                'api_response': False
            })
        
        return results
