"""
API Checker Modules
Individual API checking methods for various fact-checking sources
"""
import re
import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class APICheckers:
    """Collection of API checking methods"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.google_api_key = api_keys.get('google')
        self.fred_api_key = api_keys.get('fred')
        self.openai_api_key = api_keys.get('openai')
        self.mediastack_api_key = api_keys.get('mediastack')
        self.news_api_key = api_keys.get('news')
        self.noaa_token = api_keys.get('noaa')
        self.crossref_email = api_keys.get('crossref_email', 'factchecker@example.com')
        
        # FRED series mapping
        self.fred_series = {
            'unemployment': 'UNRATE',
            'inflation': 'CPIAUCSL',
            'gdp': 'GDP',
            'interest rate': 'DFF',
            'federal funds': 'DFF',
            'jobs': 'PAYEMS',
            'employment': 'PAYEMS',
            'retail sales': 'RSXFS',
            'housing starts': 'HOUST',
            'consumer confidence': 'UMCSENT',
            'manufacturing': 'IPMAN',
            'recession': 'USREC'
        }
    
    async def check_google_factcheck(self, claim: str) -> Dict:
        """Check Google Fact Check API"""
        if not self.google_api_key:
            return {'found': False}
        
        try:
            params = {
                'key': self.google_api_key,
                'query': claim[:200],
                'languageCode': 'en'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://factchecktools.googleapis.com/v1alpha1/claims:search',
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('claims'):
                            claim_data = data['claims'][0]
                            review = claim_data.get('claimReview', [{}])[0]
                            
                            return {
                                'found': True,
                                'verdict': review.get('textualRating', 'unverified'),
                                'confidence': 85,
                                'explanation': review.get('title', 'Verified by fact-checkers'),
                                'source': 'Google Fact Check',
                                'publisher': review.get('publisher', {}).get('name', 'Unknown'),
                                'url': review.get('url', ''),
                                'weight': 0.9
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {str(e)}")
            return {'found': False}
    
    async def analyze_with_openai(self, claim: str) -> Dict:
        """Use OpenAI for claim analysis"""
        if not self.openai_api_key:
            return {'found': False}
        
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""Analyze this claim for factual accuracy: "{claim}"
            
            Consider:
            1. Is this claim verifiable?
            2. What specific facts need checking?
            3. Is the claim misleading even if technically true?
            4. What important context is missing?
            5. Has this claim been debunked before?
            
            Categorize as: true, mostly_true, misleading, lacks_context, mixed, mostly_false, false, or unsubstantiated.
            
            Provide a brief, specific assessment."""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are a professional fact-checker. Be specific and cite examples when possible.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 300
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('choices'):
                            analysis = result['choices'][0]['message']['content']
                            
                            return {
                                'found': True,
                                'verdict': 'mixed',  # Will be extracted by verdict processor
                                'confidence': 75,
                                'explanation': analysis[:300],
                                'source': 'OpenAI Analysis',
                                'weight': 0.7,
                                'raw_analysis': analysis
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {'found': False}
    
    async def check_fred_data(self, claim: str) -> Dict:
        """Check economic claims against FRED data"""
        if not self.fred_api_key:
            return {'found': False}
        
        try:
            claim_lower = claim.lower()
            
            for indicator, series_id in self.fred_series.items():
                if indicator in claim_lower:
                    numbers = re.findall(r'\d+\.?\d*', claim)
                    if not numbers:
                        continue
                    
                    url = f"https://api.stlouisfed.org/fred/series/observations"
                    params = {
                        'series_id': series_id,
                        'api_key': self.fred_api_key,
                        'file_type': 'json',
                        'sort_order': 'desc',
                        'limit': 10
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if data.get('observations'):
                                    latest_value = float(data['observations'][0]['value'])
                                    claim_value = float(numbers[0])
                                    
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
                                        verdict = 'mostly_false'
                                        confidence = 85
                                    
                                    return {
                                        'found': True,
                                        'verdict': verdict,
                                        'confidence': confidence,
                                        'explanation': f"FRED data shows {indicator} at {latest_value} (claim: {claim_value})",
                                        'source': 'Federal Reserve Economic Data',
                                        'weight': 0.95
                                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"FRED API error: {str(e)}")
            return {'found': False}
    
    async def check_wikipedia(self, claim: str) -> Dict:
        """Check claims against Wikipedia"""
        try:
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:3])
            
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': search_query,
                'srlimit': 3
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('query', {}).get('search'):
                            page_id = data['query']['search'][0]['pageid']
                            
                            content_params = {
                                'action': 'query',
                                'format': 'json',
                                'pageids': page_id,
                                'prop': 'extracts',
                                'exintro': True,
                                'explaintext': True,
                                'exsentences': 5
                            }
                            
                            async with session.get(search_url, params=content_params) as content_response:
                                if content_response.status == 200:
                                    content_data = await content_response.json()
                                    
                                    pages = content_data.get('query', {}).get('pages', {})
                                    if pages:
                                        extract = list(pages.values())[0].get('extract', '')
                                        
                                        matches = sum(1 for term in key_terms if term.lower() in extract.lower())
                                        
                                        if matches >= 2:
                                            return {
                                                'found': True,
                                                'verdict': 'mostly_true',
                                                'confidence': 70,
                                                'explanation': f"Wikipedia entry supports this claim",
                                                'source': 'Wikipedia',
                                                'weight': 0.6
                                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Wikipedia API error: {str(e)}")
            return {'found': False}
    
    async def check_semantic_scholar(self, claim: str) -> Dict:
        """Check academic claims"""
        try:
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:4])
            
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': search_query,
                'fields': 'title,abstract,year,citationCount',
                'limit': 5
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('data'):
                            high_citation_papers = [p for p in data['data'] if p.get('citationCount', 0) > 10]
                            
                            if high_citation_papers:
                                return {
                                    'found': True,
                                    'verdict': 'mostly_true',
                                    'confidence': 75,
                                    'explanation': f"Found {len(high_citation_papers)} peer-reviewed papers supporting this",
                                    'source': 'Semantic Scholar',
                                    'weight': 0.8
                                }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Semantic Scholar API error: {str(e)}")
            return {'found': False}
    
    async def check_cdc_data(self, claim: str) -> Dict:
        """Check health claims against CDC data"""
        try:
            claim_lower = claim.lower()
            health_keywords = ['covid', 'vaccine', 'disease', 'mortality', 'health', 'cdc']
            
            if not any(keyword in claim_lower for keyword in health_keywords):
                return {'found': False}
            
            if 'covid' in claim_lower:
                endpoint = "https://data.cdc.gov/resource/9mfq-cb36.json"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(endpoint, params={'$limit': 10}, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data:
                                return {
                                    'found': True,
                                    'verdict': 'mixed',
                                    'confidence': 65,
                                    'explanation': "CDC data available for verification",
                                    'source': 'CDC Data',
                                    'weight': 0.85
                                }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"CDC API error: {str(e)}")
            return {'found': False}
    
    async def check_news_sources(self, claim: str) -> Dict:
        """Check news sources for claim verification"""
        if self.mediastack_api_key:
            return await self._check_mediastack_news(claim)
        elif self.news_api_key:
            return await self._check_newsapi(claim)
        else:
            return {'found': False}
    
    async def _check_mediastack_news(self, claim: str) -> Dict:
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
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('data'):
                            article_count = len(data['data'])
                            return {
                                'found': True,
                                'verdict': 'mixed',
                                'confidence': 60,
                                'explanation': f"Found {article_count} recent news articles discussing this",
                                'source': 'MediaStack News',
                                'weight': 0.7
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"MediaStack API error: {str(e)}")
            return {'found': False}
    
    async def _check_newsapi(self, claim: str) -> Dict:
        """Check News API"""
        try:
            key_terms = self._extract_key_terms(claim)
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.news_api_key,
                'q': ' '.join(key_terms[:3]),
                'sortBy': 'relevancy',
                'pageSize': 5,
                'language': 'en'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('articles'):
                            return {
                                'found': True,
                                'verdict': 'mixed',
                                'confidence': 60,
                                'explanation': f'Found {len(data["articles"])} related news articles',
                                'source': 'News API',
                                'weight': 0.65
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"News API error: {str(e)}")
            return {'found': False}
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key search terms from claim"""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be'}
        
        words = claim.split()
        key_terms = []
        
        # Keep proper nouns
        for word in words:
            if word[0].isupper() and word.lower() not in stop_words:
                key_terms.append(word)
        
        # Keep numbers
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        key_terms.extend(numbers)
        
        # Keep remaining important words
        remaining_words = [w for w in words if w.lower() not in stop_words and w not in key_terms]
        key_terms.extend(remaining_words[:3])
        
        return key_terms[:5]
