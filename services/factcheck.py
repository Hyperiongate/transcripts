"""
Enhanced Fact Checking Service - Complete Working Implementation
Coordinates fact-checking using multiple sources with all features
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
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Enhanced fact-checking with speaker context and comprehensive analysis"""
    
    def __init__(self):
        # Initialize ALL API keys
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.fred_api_key = Config.FRED_API_KEY
        self.news_api_key = Config.NEWS_API_KEY
        self.mediastack_api_key = Config.MEDIASTACK_API_KEY
        self.openai_api_key = Config.OPENAI_API_KEY
        self.scraperapi_key = Config.SCRAPERAPI_KEY
        self.scrapingbee_api_key = Config.SCRAPINGBEE_API_KEY
        
        # Known speaker backgrounds (should be in a database in production)
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
            }
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
        
        logger.info(f"✅ Active fact-checking APIs: {', '.join(active_apis)}")
    
    def get_speaker_context(self, speaker_name: str) -> Dict:
        """Get comprehensive background on speaker"""
        if not speaker_name:
            return {}
        
        logger.info(f"Looking up speaker context for: {speaker_name}")
        
        # Check for Trump in various forms
        trump_variants = ['trump', 'donald trump', 'president trump']
        if any(variant in speaker_name.lower() for variant in trump_variants):
            logger.info("Identified as Donald Trump - returning full context")
            return {
                'speaker': 'Donald Trump',
                'has_criminal_record': True,
                'criminal_record': 'Convicted felon - 34 counts of falsifying business records (May 2024)',
                'fraud_history': 'Found liable for civil fraud - inflating wealth to obtain favorable loans and insurance rates ($355 million penalty)',
                'fact_check_history': 'Made over 30,000 false or misleading claims during presidency (Washington Post)',
                'credibility_notes': 'Documented pattern of making false statements about wealth, achievements, and political opponents',
                'legal_issues': [
                    'Criminal conviction for business fraud (2024)',
                    'Civil fraud judgment - $355 million penalty',
                    'Multiple ongoing criminal cases'
                ]
            }
        
        # Check for Biden
        biden_variants = ['biden', 'joe biden', 'president biden']
        if any(variant in speaker_name.lower() for variant in biden_variants):
            return {
                'speaker': 'Joe Biden',
                'credibility_notes': 'Generally factual but prone to exaggeration and misremembering details',
                'fact_check_history': 'Mixed record - some false claims but far fewer than predecessor'
            }
        
        # Check if just "President" - need more context
        if speaker_name.lower() == 'president':
            # Could check date or source to determine which president
            # For now, return generic
            return {
                'speaker': speaker_name,
                'credibility_notes': 'Unable to determine specific president from context'
            }
        
        # Check exact matches
        for known_speaker, info in self.speaker_backgrounds.items():
            if known_speaker.lower() in speaker_name.lower():
                return {
                    'speaker': known_speaker,
                    'has_criminal_record': 'criminal_record' in info,
                    **info
                }
        
        return {'speaker': speaker_name, 'credibility_notes': 'No prior fact-checking history available'}
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims using ALL available APIs comprehensively"""
        results = []
        
        # Check all claims with comprehensive checking
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_claim = {
                executor.submit(self.check_claim_comprehensive, claim): claim 
                for claim in claims
            }
            
            for future in as_completed(future_to_claim):
                claim = future_to_claim[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error checking claim '{claim}': {str(e)}")
                    results.append(self._create_error_result(claim))
        
        return results
    
    def check_claim_comprehensive(self, claim: str) -> Dict:
        """Check claim using ALL available resources comprehensively"""
        logger.info(f"Comprehensive check for: {claim[:80]}...")
        
        all_results = []
        
        # 1. Google Fact Check - Primary source
        if self.google_api_key:
            result = self._check_google_factcheck(claim)
            if result['found']:
                all_results.append(result)
        
        # 2. FRED for economic data
        if self.fred_api_key and self._is_economic_claim(claim):
            result = self._check_fred_data(claim)
            if result['found']:
                all_results.append(result)
        
        # 3. News API for current events
        if self.news_api_key:
            result = self._check_news_api(claim)
            if result['found']:
                all_results.append(result)
        
        # 4. MediaStack for additional news
        if self.mediastack_api_key:
            result = self._check_mediastack(claim)
            if result['found']:
                all_results.append(result)
        
        # 5. Web scraping for fact-checker sites
        if self.scraperapi_key or self.scrapingbee_api_key:
            result = self._check_factchecker_sites(claim)
            if result['found']:
                all_results.append(result)
        
        # 6. Wikipedia for established facts
        result = self._check_wikipedia(claim)
        if result['found']:
            all_results.append(result)
        
        # 7. OpenAI for complex analysis (especially if no other results)
        if self.openai_api_key:
            result = self._analyze_with_ai(claim, all_results)
            if result['found']:
                all_results.append(result)
        
        # Synthesize comprehensive result
        return self._synthesize_comprehensive_result(claim, all_results)
    
    def check_claim(self, claim: str) -> Dict:
        """Standard claim checking for backward compatibility"""
        return self.check_claim_comprehensive(claim)
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Enhanced Google Fact Check with better parsing"""
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],
                'languageCode': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('claims'):
                    claim_data = data['claims'][0]
                    reviews = claim_data.get('claimReview', [])
                    
                    if reviews:
                        review = reviews[0]
                        rating = review.get('textualRating', '')
                        
                        # Enhanced verdict mapping
                        verdict = self._enhanced_verdict_mapping(rating, review.get('title', ''))
                        
                        return {
                            'found': True,
                            'verdict': verdict,
                            'confidence': 90,
                            'explanation': self._create_detailed_explanation(
                                verdict, 
                                review.get('title', ''),
                                review.get('publisher', {}).get('name', 'fact-checker')
                            ),
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
        """Enhanced FRED check with better explanations"""
        try:
            numbers = re.findall(r'\d+\.?\d*', claim)
            if not numbers:
                return {'found': False}
            
            claim_lower = claim.lower()
            
            # Expanded economic indicators
            series_map = {
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
            
            for keyword, (series_id, description) in series_map.items():
                if keyword in claim_lower:
                    url = "https://api.stlouisfed.org/fred/series/observations"
                    params = {
                        'series_id': series_id,
                        'api_key': self.fred_api_key,
                        'file_type': 'json',
                        'sort_order': 'desc',
                        'limit': 1
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    
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
                            
                            # Determine verdict with context
                            if diff_pct < 2:
                                verdict = 'true'
                                accuracy = "exactly correct"
                            elif diff_pct < 5:
                                verdict = 'mostly_true'
                                accuracy = "very close"
                            elif diff_pct < 10:
                                verdict = 'mostly_true'
                                accuracy = "approximately correct"
                            elif diff_pct < 20:
                                verdict = 'lacks_context'
                                accuracy = "outdated or imprecise"
                            else:
                                verdict = 'false'
                                accuracy = "significantly incorrect"
                            
                            explanation = (
                                f"Official {description} as of {date} is {actual_value}. "
                                f"The claim states {claim_value}, which is {accuracy} "
                                f"(difference of {diff_pct:.1f}%). Source: Federal Reserve Economic Data."
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
    
    def _check_news_api(self, claim: str) -> Dict:
        """Enhanced news checking with sentiment analysis"""
        try:
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:4])
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.news_api_key,
                'q': search_query,
                'sortBy': 'relevancy',
                'pageSize': 10,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                if len(articles) >= 3:
                    # Analyze article titles and descriptions
                    supporting = 0
                    contradicting = 0
                    sources = set()
                    
                    for article in articles:
                        source = article.get('source', {}).get('name', 'Unknown')
                        sources.add(source)
                        
                        # Simple sentiment analysis
                        title = article.get('title', '').lower()
                        desc = article.get('description', '').lower()
                        combined = title + ' ' + desc
                        
                        # Check for contradictions
                        if any(word in combined for word in ['false', 'debunk', 'myth', 'incorrect', 'wrong']):
                            contradicting += 1
                        elif any(word in combined for word in ['confirm', 'true', 'correct', 'verify']):
                            supporting += 1
                    
                    # Create meaningful explanation
                    if contradicting > supporting:
                        verdict = 'mostly_false'
                        sentiment = "Multiple news sources contradict this claim"
                    elif supporting > contradicting:
                        verdict = 'mostly_true'
                        sentiment = "Multiple news sources support this claim"
                    else:
                        verdict = 'unverified'
                        sentiment = "News coverage is mixed or inconclusive"
                    
                    explanation = (
                        f"{sentiment}. Found {len(articles)} relevant articles from "
                        f"sources including: {', '.join(list(sources)[:3])}. "
                    )
                    
                    return {
                        'found': True,
                        'verdict': verdict,
                        'confidence': 70,
                        'explanation': explanation,
                        'source': 'News API Analysis',
                        'weight': 0.7
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"News API error: {str(e)}")
            return {'found': False}
    
    def _check_mediastack(self, claim: str) -> Dict:
        """Check MediaStack news API with better analysis"""
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
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    articles = data['data']
                    sources = set(art.get('source', 'Unknown') for art in articles)
                    
                    # Analyze content
                    relevant_count = 0
                    for article in articles:
                        title = article.get('title', '').lower()
                        if any(term.lower() in title for term in key_terms[:3]):
                            relevant_count += 1
                    
                    if relevant_count >= 3:
                        explanation = (
                            f"Found {len(articles)} recent news articles from {len(sources)} sources "
                            f"including: {', '.join(list(sources)[:3])}. "
                            f"{relevant_count} articles directly address this topic."
                        )
                        verdict = 'unverified'  # News presence doesn't confirm truth
                        confidence = 65
                    else:
                        explanation = f"Limited news coverage found from: {', '.join(list(sources)[:3])}"
                        verdict = 'unverified'
                        confidence = 50
                    
                    return {
                        'found': True,
                        'verdict': verdict,
                        'confidence': confidence,
                        'explanation': explanation,
                        'source': 'MediaStack News',
                        'weight': 0.6
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"MediaStack error: {str(e)}")
            return {'found': False}
    
    def _check_factchecker_sites(self, claim: str) -> Dict:
        """Check major fact-checking websites"""
        try:
            # Sites to check
            fact_checkers = [
                ('snopes.com', 'Snopes'),
                ('factcheck.org', 'FactCheck.org'),
                ('politifact.com', 'PolitiFact')
            ]
            
            results = []
            
            for domain, name in fact_checkers:
                # Use web scraping API to search the site
                if self.scraperapi_key:
                    search_url = f"https://www.{domain}/search/?q={requests.utils.quote(claim[:100])}"
                    scraper_url = f"http://api.scraperapi.com?api_key={self.scraperapi_key}&url={search_url}"
                    
                    try:
                        response = requests.get(scraper_url, timeout=15)
                        if response.status_code == 200:
                            # Check if claim appears in results
                            if any(term.lower() in response.text.lower() for term in claim.split()[:5]):
                                results.append(name)
                    except:
                        pass
            
            if results:
                return {
                    'found': True,
                    'verdict': 'mixed',
                    'confidence': 75,
                    'explanation': f"Found related fact-checks on: {', '.join(results)}",
                    'source': 'Fact-Checking Websites',
                    'weight': 0.8
                }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Fact-checker sites error: {str(e)}")
            return {'found': False}
    
    def _check_wikipedia(self, claim: str) -> Dict:
        """Check Wikipedia for established facts"""
        try:
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:3])
            
            # Wikipedia API
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': search_query,
                'srlimit': 3
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('query', {}).get('search', [])
                
                if search_results:
                    # Get page content
                    page_id = search_results[0]['pageid']
                    content_params = {
                        'action': 'query',
                        'format': 'json',
                        'pageids': page_id,
                        'prop': 'extracts',
                        'exintro': True,
                        'explaintext': True,
                        'exsentences': 5
                    }
                    
                    content_response = requests.get(search_url, params=content_params, timeout=10)
                    if content_response.status_code == 200:
                        content_data = content_response.json()
                        pages = content_data.get('query', {}).get('pages', {})
                        
                        if pages:
                            extract = list(pages.values())[0].get('extract', '')
                            
                            # Check if claim aligns with Wikipedia content
                            claim_terms = set(term.lower() for term in claim.split())
                            wiki_terms = set(term.lower() for term in extract.split())
                            overlap = len(claim_terms & wiki_terms)
                            
                            if overlap > len(claim_terms) * 0.3:
                                return {
                                    'found': True,
                                    'verdict': 'mostly_true',
                                    'confidence': 70,
                                    'explanation': f"Wikipedia entry on '{search_results[0]['title']}' provides context supporting this claim.",
                                    'source': 'Wikipedia',
                                    'weight': 0.6
                                }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Wikipedia error: {str(e)}")
            return {'found': False}
    
    def _analyze_with_ai(self, claim: str, other_results: List[Dict]) -> Dict:
        """Use AI to analyze claim with context from other checks"""
        if not self.openai_api_key:
            return {'found': False}
        
        try:
            # Prepare context from other checks
            context = "Previous checks:\n"
            for result in other_results:
                context += f"- {result['source']}: {result['verdict']} - {result.get('explanation', '')[:100]}\n"
            
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""As a professional fact-checker, analyze this claim with the following context:

Claim: "{claim}"

{context if other_results else "No other fact-checks available."}

Determine:
1. Is this claim deliberately deceptive, a simple error, or factually accurate?
2. What important context is missing?
3. Final verdict: true, mostly_true, lacks_context, deceptive, mostly_false, or false

Respond in JSON format:
{{"verdict": "", "confidence": 0-100, "explanation": "", "is_deceptive": true/false}}"""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are an expert fact-checker.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 300
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                try:
                    analysis = json.loads(content)
                    
                    # Never use 'mixed' - convert to more specific verdict
                    if analysis.get('verdict') == 'mixed':
                        analysis['verdict'] = 'lacks_context' if not analysis.get('is_deceptive') else 'deceptive'
                    
                    return {
                        'found': True,
                        'verdict': analysis['verdict'],
                        'confidence': analysis['confidence'],
                        'explanation': analysis['explanation'],
                        'source': 'AI Deep Analysis',
                        'weight': 0.8
                    }
                except:
                    return {'found': False}
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            return {'found': False}
    
    def _synthesize_comprehensive_result(self, claim: str, all_results: List[Dict]) -> Dict:
        """Create comprehensive result from all checks"""
        if not all_results:
            return {
                'claim': claim,
                'verdict': 'unverified',
                'confidence': 0,
                'explanation': 'No fact-checking sources could verify this claim.',
                'sources': [],
                'api_response': False
            }
        
        # Weight verdicts
        verdict_weights = defaultdict(float)
        total_weight = 0
        explanations = []
        sources = []
        highest_confidence = 0
        
        for result in all_results:
            weight = result.get('weight', 0.5)
            verdict = result.get('verdict', 'unverified')
            
            # Never use 'mixed' - convert to more specific verdict
            if verdict == 'mixed':
                verdict = 'lacks_context'
            
            verdict_weights[verdict] += weight
            total_weight += weight
            
            explanations.append(result.get('explanation', ''))
            sources.append(result.get('source', 'Unknown'))
            highest_confidence = max(highest_confidence, result.get('confidence', 0))
        
        # Determine final verdict
        final_verdict = max(verdict_weights.items(), key=lambda x: x[1])[0]
        
        # Create comprehensive explanation
        explanation = self._create_comprehensive_explanation(
            final_verdict,
            explanations,
            sources,
            len(all_results)
        )
        
        return {
            'claim': claim,
            'verdict': final_verdict,
            'confidence': highest_confidence,
            'explanation': explanation,
            'sources': sources,
            'source_count': len(all_results),
            'api_response': True
        }
    
    def _create_comprehensive_explanation(self, verdict: str, explanations: List[str], 
                                        sources: List[str], source_count: int) -> str:
        """Create detailed, meaningful explanation"""
        # Start with verdict summary
        verdict_intros = {
            'true': "This claim is accurate.",
            'mostly_true': "This claim is largely accurate with minor caveats.",
            'lacks_context': "This claim omits important context that changes its meaning.",
            'deceptive': "This claim appears deliberately misleading.",
            'mostly_false': "This claim is largely inaccurate.",
            'false': "This claim is demonstrably false.",
            'unverified': "This claim cannot be verified with available sources."
        }
        
        explanation = verdict_intros.get(verdict, "Unable to determine accuracy.")
        
        # Add key findings
        if explanations:
            key_finding = next((e for e in explanations if len(e) > 20), None)
            if key_finding:
                explanation += f" {key_finding}"
        
        # Add source summary
        explanation += f" Verified using {source_count} sources"
        if source_count > 0:
            unique_sources = list(set(sources))[:3]
            explanation += f" including {', '.join(unique_sources)}."
        
        return explanation
    
    def _enhanced_verdict_mapping(self, rating: str, title: str = '') -> str:
        """Map ratings to verdicts, avoiding 'mixed'"""
        rating_lower = rating.lower()
        title_lower = title.lower() if title else ''
        
        # Check for deception indicators
        if any(word in rating_lower + title_lower for word in 
               ['misleading', 'deceptive', 'manipulated', 'distorted', 'spin']):
            return 'deceptive'
        
        # Check for context issues
        if any(word in rating_lower + title_lower for word in 
               ['lacks context', 'missing context', 'needs context', 'out of context']):
            return 'lacks_context'
        
        # Standard mappings
        if 'true' in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_true'
            return 'true'
        
        if 'false' in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_false'
            return 'false'
        
        # Instead of 'mixed', determine if it's deceptive or lacks context
        if any(word in rating_lower for word in ['mixed', 'mixture', 'half']):
            # Look for intent in the explanation
            if 'intent' in title_lower or 'mislead' in title_lower:
                return 'deceptive'
            else:
                return 'lacks_context'
        
        return 'unverified'
    
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
    
    def _create_detailed_explanation(self, verdict: str, title: str, publisher: str) -> str:
        """Create detailed explanation from fact-check results"""
        if 'deceptive' in verdict:
            return f"{publisher} found this claim to be deliberately misleading. {title}"
        elif 'false' in verdict:
            return f"{publisher} verified this claim as false. {title}"
        elif 'true' in verdict:
            return f"{publisher} confirmed this claim as accurate. {title}"
        else:
            return f"{publisher}: {title}"
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> int:
        """Calculate overall credibility score"""
        if not fact_checks:
            return 50
        
        scores = {
            'true': 100,
            'mostly_true': 75,
            'lacks_context': 40,
            'deceptive': 20,  # Heavily penalize deception
            'mostly_false': 25,
            'false': 0,
            'unverified': 50
        }
        
        total_score = sum(scores.get(fc.get('verdict', 'unverified'), 50) for fc in fact_checks)
        return int(total_score / len(fact_checks))
