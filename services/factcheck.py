"""
Enhanced Fact Checking Service with Multiple Verification Sources
Complete version with FRED, Semantic Scholar, and MediaStack integrations
"""
import os
import time
import logging
import requests
import asyncio
import aiohttp
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import json

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Multi-source fact checker with real verification capabilities"""
    
    def __init__(self):
        # API Keys
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.news_api_key = getattr(Config, 'NEWS_API_KEY', None)
        self.scraperapi_key = getattr(Config, 'SCRAPERAPI_KEY', None)
        self.fred_api_key = getattr(Config, 'FRED_API_KEY', None)
        self.mediastack_api_key = getattr(Config, 'MEDIASTACK_API_KEY', None)
        
        self.session = requests.Session()
        
        # Define clear verdict meanings
        self.verdict_definitions = {
            'true': 'The claim is accurate and supported by evidence',
            'mostly_true': 'The claim is largely accurate with minor caveats',
            'mixed': 'The claim contains both true and false elements',
            'mostly_false': 'The claim is largely inaccurate with a grain of truth',
            'false': 'The claim is demonstrably false',
            'unverified': 'Insufficient evidence to determine truth'
        }
        
        # FRED series mapping for economic data
        self.fred_series = {
            'unemployment rate': 'UNRATE',
            'unemployment': 'UNRATE',
            'jobless rate': 'UNRATE',
            'inflation rate': 'CPIAUCSL',
            'inflation': 'CPIAUCSL',
            'cpi': 'CPIAUCSL',
            'gdp': 'GDP',
            'gross domestic product': 'GDP',
            'gdp growth': 'GDPC1',
            'interest rate': 'DFF',
            'federal funds': 'DFF',
            'mortgage rate': 'MORTGAGE30US',
            'gas price': 'GASREGW',
            'oil price': 'DCOILWTICO',
            'stock market': 'SP500',
            's&p 500': 'SP500',
            's&p': 'SP500',
            'dow jones': 'DJIA',
            'dow': 'DJIA',
            'nasdaq': 'NASDAQCOM',
            'minimum wage': 'FEDMINNFRWG',
            'jobs': 'PAYEMS',
            'employment': 'PAYEMS',
            'job openings': 'JTSJOL',
            'retail sales': 'RSXFS',
            'consumer confidence': 'UMCSENT',
            'housing starts': 'HOUST',
            'home sales': 'HSN1F',
            'trade deficit': 'BOPGSTB',
            'national debt': 'GFDEBTN',
        }
    
    def check_claim(self, claim: str) -> Dict:
        """Check if a claim is TRUE or FALSE, not who said it"""
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._async_check_claim(claim))
            return result
        finally:
            loop.close()
    
    async def _async_check_claim(self, claim: str) -> Dict:
        """Verify the truth of a claim using multiple methods"""
        
        # Check if it's an economic claim
        claim_lower = claim.lower()
        economic_terms = list(self.fred_series.keys()) + ['economy', 'economic', 'recession', 'growth']
        is_economic = any(term in claim_lower for term in economic_terms)
        
        # Check if it's an academic/research claim
        research_terms = ['study', 'research', 'scientists', 'researchers', 'paper', 'journal', 
                         'university', 'professor', 'academic', 'peer-reviewed', 'published']
        is_research = any(term in claim_lower for term in research_terms)
        
        # Build task list based on claim type
        tasks = []
        
        # Always check Google Fact Check
        tasks.append(self._check_google_factcheck(claim))
        
        # Add FRED for economic claims
        if is_economic and self.fred_api_key:
            tasks.append(self._check_fred_data(claim))
        
        # Add Semantic Scholar for research claims
        if is_research:
            tasks.append(self._check_semantic_scholar(claim))
        
        # Add news verification (MediaStack preferred, fallback to News API)
        if self.mediastack_api_key:
            tasks.append(self._check_mediastack_news(claim))
        elif self.news_api_key:
            tasks.append(self._search_news_verification(claim))
        
        # Gather all results
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results focusing on TRUTH
        valid_results = [r for r in all_results if isinstance(r, dict) and r.get('found')]
        
        if not valid_results:
            return self._create_unverified_response(claim, "No verification sources available")
        
        # Synthesize based on agreement about TRUTH
        return self._synthesize_truth_verdict(claim, valid_results)
    
    async def _check_google_factcheck(self, claim: str) -> Dict:
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
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'claims' in data and data['claims']:
                            return self._process_google_factcheck(data['claims'][0])
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google API error: {str(e)}")
            return {'found': False}
    
    def _process_google_factcheck(self, claim_data: Dict) -> Dict:
        """Process Google fact check focusing on TRUTH verdict"""
        if 'claimReview' in claim_data and claim_data['claimReview']:
            review = claim_data['claimReview'][0]
            
            rating = review.get('textualRating', '')
            verdict = self._normalize_truth_verdict(rating)
            
            return {
                'found': True,
                'verdict': verdict,
                'explanation': review.get('title', ''),
                'source': review.get('publisher', {}).get('name', 'Fact Checker'),
                'url': review.get('url', ''),
                'confidence': 85 if verdict != 'unverified' else 40,
                'weight': 0.9
            }
        return {'found': False}
    
    async def _check_fred_data(self, claim: str) -> Dict:
        """Verify economic claims against Federal Reserve data"""
        
        if not self.fred_api_key:
            return {'found': False}
        
        try:
            # Check if claim contains economic indicators
            claim_lower = claim.lower()
            series_to_check = []
            
            for term, series_id in self.fred_series.items():
                if term in claim_lower:
                    series_to_check.append((term, series_id))
            
            if not series_to_check:
                return {'found': False}
            
            # Extract numbers from claim
            numbers = re.findall(r'(\d+\.?\d*)\s*%?', claim)
            if not numbers:
                return {'found': False}
            
            claimed_value = float(numbers[0])
            
            # Check the most relevant series
            term, series_id = series_to_check[0]
            
            # Get latest data from FRED
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                'series_id': series_id,
                'api_key': self.fred_api_key,
                'file_type': 'json',
                'sort_order': 'desc',
                'limit': 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('observations'):
                            latest = data['observations'][0]
                            actual_value = float(latest['value'])
                            date = latest['date']
                            
                            # Compare claimed vs actual
                            difference = abs(actual_value - claimed_value)
                            percentage_diff = (difference / actual_value) * 100 if actual_value != 0 else 100
                            
                            # Determine verdict based on accuracy
                            if percentage_diff < 1:
                                verdict = 'true'
                                confidence = 95
                            elif percentage_diff < 5:
                                verdict = 'mostly_true'
                                confidence = 85
                            elif percentage_diff < 10:
                                verdict = 'mixed'
                                confidence = 70
                            elif percentage_diff < 20:
                                verdict = 'mostly_false'
                                confidence = 80
                            else:
                                verdict = 'false'
                                confidence = 90
                            
                            explanation = f"Federal Reserve data shows {term} is actually {actual_value}% as of {date}"
                            if verdict == 'true':
                                explanation = f"✓ Verified: {term} is {actual_value}% as of {date}"
                            elif verdict == 'false':
                                explanation = f"✗ Incorrect: {term} is actually {actual_value}% as of {date}, not {claimed_value}%"
                            
                            return {
                                'found': True,
                                'verdict': verdict,
                                'confidence': confidence,
                                'explanation': explanation,
                                'source': 'Federal Reserve Economic Data (FRED)',
                                'url': f'https://fred.stlouisfed.org/series/{series_id}',
                                'actual_value': actual_value,
                                'claimed_value': claimed_value,
                                'date': date,
                                'weight': 0.95
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"FRED API error: {str(e)}")
            return {'found': False}
    
    async def _check_semantic_scholar(self, claim: str) -> Dict:
        """Check claim against academic literature - NO API KEY NEEDED"""
        
        research_indicators = ['study', 'research', 'scientists', 'researchers', 'paper', 'journal', 
                              'university', 'professor', 'academic', 'peer-reviewed', 'published']
        
        claim_lower = claim.lower()
        if not any(indicator in claim_lower for indicator in research_indicators):
            return {'found': False}
        
        try:
            # Clean claim for search
            search_query = re.sub(r'(according to|study shows|research indicates|scientists say)', '', claim, flags=re.IGNORECASE)
            search_query = search_query.strip()[:200]
            
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': search_query,
                'limit': 5,
                'fields': 'title,abstract,year,citationCount,journal,authors,isOpenAccess,tldr'
            }
            
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': 'FactChecker/1.0'}
                
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('data') and len(data['data']) > 0:
                            papers = data['data']
                            
                            # Analyze papers for relevance and consensus
                            high_quality_papers = [p for p in papers if p.get('citationCount', 0) > 10]
                            
                            if high_quality_papers:
                                top_paper = high_quality_papers[0]
                                
                                verdict = self._analyze_paper_alignment(claim, top_paper)
                                
                                explanation = f"Academic literature review: Found {len(high_quality_papers)} relevant peer-reviewed papers. "
                                explanation += f"Most cited: '{top_paper.get('title', 'Unknown')}' "
                                explanation += f"({top_paper.get('citationCount', 0)} citations, {top_paper.get('year', 'Unknown')})"
                                
                                if top_paper.get('tldr'):
                                    explanation += f". Summary: {top_paper['tldr'].get('text', '')[:200]}"
                                
                                return {
                                    'found': True,
                                    'verdict': verdict,
                                    'confidence': min(70 + (len(high_quality_papers) * 5), 90),
                                    'explanation': explanation,
                                    'source': 'Semantic Scholar Academic Database',
                                    'url': f"https://www.semanticscholar.org/search?q={search_query}",
                                    'paper_count': len(papers),
                                    'weight': 0.85
                                }
                            else:
                                return {
                                    'found': True,
                                    'verdict': 'unverified',
                                    'confidence': 40,
                                    'explanation': f"Found {len(papers)} papers but none with significant citations. More research needed.",
                                    'source': 'Semantic Scholar Academic Database',
                                    'weight': 0.5
                                }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Semantic Scholar error: {str(e)}")
            return {'found': False}
    
    async def _check_mediastack_news(self, claim: str) -> Dict:
        """Verify claims using MediaStack's 7,500+ news sources"""
        
        if not self.mediastack_api_key:
            return {'found': False}
        
        try:
            # Extract key terms for news search
            key_terms = self._extract_key_terms(claim)
            search_query = ' '.join(key_terms[:4])
            
            url = "http://api.mediastack.com/v1/news"
            params = {
                'access_key': self.mediastack_api_key,
                'keywords': search_query,
                'languages': 'en',
                'limit': 10,
                'sort': 'published_desc',
                'categories': 'general,business,politics,health,science'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('data') and len(data['data']) > 0:
                            articles = data['data']
                            return self._analyze_mediastack_coverage(claim, articles)
                        else:
                            return {'found': False, 'reason': 'No news coverage found'}
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"MediaStack API error: {str(e)}")
            return {'found': False}
    
    def _analyze_mediastack_coverage(self, claim: str, articles: List[Dict]) -> Dict:
        """Analyze news articles to verify factual claims"""
        
        reputable_sources = {
            'reuters', 'associated press', 'ap news', 'bbc', 'npr', 'the guardian',
            'the new york times', 'washington post', 'wall street journal', 'cnn',
            'financial times', 'the economist', 'bloomberg', 'forbes', 'politico'
        }
        
        quality_articles = []
        for article in articles:
            source = article.get('source', '').lower()
            if any(rep in source for rep in reputable_sources):
                quality_articles.append(article)
        
        if not quality_articles:
            quality_articles = articles
            confidence_modifier = 0.7
        else:
            confidence_modifier = 1.0
        
        claim_facts = self._extract_verifiable_facts(claim)
        
        supporting = 0
        contradicting = 0
        relevant_quotes = []
        
        for article in quality_articles[:5]:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = title + ' ' + description
            
            facts_found = sum(1 for fact in claim_facts if fact.lower() in content)
            
            if facts_found > 0:
                if any(word in content for word in ['false', 'incorrect', 'debunked', 'myth', 'not true', 'no evidence']):
                    contradicting += 1
                elif any(word in content for word in ['confirmed', 'true', 'correct', 'verified', 'evidence shows']):
                    supporting += 1
                else:
                    supporting += 0.5
                
                relevant_quotes.append({
                    'source': article.get('source'),
                    'title': article.get('title'),
                    'date': article.get('published_at')
                })
        
        if supporting > contradicting * 2:
            verdict = 'true'
            confidence = min(70 + (supporting * 5), 90) * confidence_modifier
            explanation = f"Verified by {len(quality_articles)} news sources. "
        elif contradicting > supporting * 2:
            verdict = 'false'
            confidence = min(70 + (contradicting * 5), 90) * confidence_modifier
            explanation = f"Contradicted by {len(quality_articles)} news sources. "
        elif supporting > 0 or contradicting > 0:
            verdict = 'mixed'
            confidence = 60 * confidence_modifier
            explanation = f"Mixed coverage from {len(quality_articles)} sources. "
        else:
            verdict = 'unverified'
            confidence = 30
            explanation = "Insufficient news coverage to verify. "
        
        if relevant_quotes:
            sources_list = list(set([q['source'] for q in relevant_quotes[:3]]))
            explanation += f"Key sources: {', '.join(sources_list)}"
        
        return {
            'found': True,
            'verdict': verdict,
            'confidence': int(confidence),
            'explanation': explanation,
            'source': 'MediaStack News Analysis',
            'article_count': len(articles),
            'weight': 0.75
        }
    
    async def _search_news_verification(self, claim: str) -> Dict:
        """Fallback to News API if MediaStack not available"""
        if not self.news_api_key:
            return {'found': False}
        
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
                                'weight': 0.7
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"News API error: {str(e)}")
            return {'found': False}
    
    def _synthesize_truth_verdict(self, claim: str, results: List[Dict]) -> Dict:
        """Synthesize final verdict focused on TRUTH, not attribution"""
        
        verdicts = []
        explanations = []
        sources = []
        
        for result in results:
            verdict = result.get('verdict', 'unverified')
            if verdict != 'unverified':
                verdicts.append({
                    'verdict': verdict,
                    'confidence': result.get('confidence', 50),
                    'weight': result.get('weight', 0.5),
                    'source': result.get('source', 'Unknown')
                })
                if result.get('explanation'):
                    explanations.append(f"{result['source']}: {result['explanation']}")
                sources.append(result.get('source', 'Unknown'))
        
        if not verdicts:
            return self._create_unverified_response(claim, "No sources could verify the truthfulness of this claim")
        
        final_verdict = self._calculate_consensus_verdict(verdicts)
        confidence = self._calculate_truth_confidence(verdicts)
        
        explanation = self._create_truth_explanation(final_verdict, explanations, sources)
        
        return {
            'claim': claim,
            'verdict': final_verdict,
            'confidence': confidence,
            'explanation': explanation,
            'publisher': sources[0] if sources else 'Multiple Sources',
            'url': '',
            'sources': list(set(sources)),
            'api_response': True
        }
    
    def _calculate_consensus_verdict(self, verdicts: List[Dict]) -> str:
        """Calculate consensus on TRUTH from multiple sources"""
        if not verdicts:
            return 'unverified'
        
        verdict_scores = {
            'true': 0,
            'mostly_true': 0,
            'mixed': 0,
            'mostly_false': 0,
            'false': 0
        }
        
        total_weight = 0
        for v in verdicts:
            verdict = v['verdict']
            weight = v['weight'] * (v['confidence'] / 100)
            if verdict in verdict_scores:
                verdict_scores[verdict] += weight
                total_weight += weight
        
        if total_weight == 0:
            return 'unverified'
        
        best_verdict = max(verdict_scores.items(), key=lambda x: x[1])
        
        if best_verdict[1] / total_weight < 0.6:
            return 'mixed'
        
        return best_verdict[0]
    
    def _calculate_truth_confidence(self, verdicts: List[Dict]) -> int:
        """Calculate confidence in truth verdict"""
        if not verdicts:
            return 0
        
        base_confidence = min(len(verdicts) * 25, 75)
        
        verdict_types = [v['verdict'] for v in verdicts]
        unique_verdicts = set(verdict_types)
        
        if len(unique_verdicts) == 1:
            agreement_bonus = 20
        elif len(unique_verdicts) == 2:
            agreement_bonus = 10
        else:
            agreement_bonus = 0
        
        # Boost for high-weight sources
        weight_bonus = sum(v['weight'] * 5 for v in verdicts if v['weight'] > 0.8)
        
        return min(int(base_confidence + agreement_bonus + weight_bonus), 95)
    
    def _create_truth_explanation(self, verdict: str, explanations: List[str], sources: List[str]) -> str:
        """Create clear explanation of WHY claim is true/false"""
        
        verdict_meaning = self.verdict_definitions.get(verdict, '')
        
        if verdict == 'true':
            prefix = "✓ TRUE: "
        elif verdict == 'false':
            prefix = "✗ FALSE: "
        elif verdict == 'mostly_true':
            prefix = "◐ MOSTLY TRUE: "
        elif verdict == 'mostly_false':
            prefix = "◑ MOSTLY FALSE: "
        elif verdict == 'mixed':
            prefix = "◓ MIXED: "
        else:
            prefix = "? UNVERIFIED: "
        
        if explanations:
            evidence = explanations[0] if len(explanations) == 1 else f"Multiple sources report: {'; '.join(explanations[:2])}"
            return f"{prefix}{verdict_meaning}. {evidence}"
        else:
            return f"{prefix}{verdict_meaning}. Verified by {len(sources)} source(s)."
    
    def _create_unverified_response(self, claim: str, reason: str) -> Dict:
        """Create response when unable to verify"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': f"? UNVERIFIED: {reason}",
            'publisher': 'No Sources Available',
            'url': '',
            'sources': [],
            'api_response': False
        }
    
    def _normalize_truth_verdict(self, rating: str) -> str:
        """Normalize ratings to truth-focused verdicts"""
        rating_lower = rating.lower()
        
        if any(word in rating_lower for word in ['true', 'correct', 'accurate', 'fact', 'confirmed', 'yes']):
            if any(qualifier in rating_lower for qualifier in ['mostly', 'partly', 'largely', 'substantially']):
                return 'mostly_true'
            return 'true'
        
        elif any(word in rating_lower for word in ['false', 'incorrect', 'wrong', 'fake', 'debunked', 'no']):
            if any(qualifier in rating_lower for qualifier in ['mostly', 'partly', 'largely', 'substantially']):
                return 'mostly_false'
            return 'false'
        
        elif any(word in rating_lower for word in ['mixed', 'half', 'partially', 'complicated', 'partly true', 'partly false']):
            return 'mixed'
        
        else:
            return 'unverified'
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key terms for search"""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were'}
        
        words = claim.lower().split()
        key_terms = [w for w in words if w not in stop_words and len(w) > 3]
        
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', claim)
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        
        return capitalized + numbers + key_terms[:5]
    
    def _extract_verifiable_facts(self, claim: str) -> List[str]:
        """Extract specific facts that can be verified"""
        claim = re.sub(r'(according to|says|claims|stated|reported).*?,', '', claim, flags=re.IGNORECASE)
        
        facts = []
        
        numbers = re.findall(r'\d+\.?\d*%?', claim)
        facts.extend(numbers)
        
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', claim)
        facts.extend(proper_nouns)
        
        keywords = ['first', 'largest', 'smallest', 'only', 'never', 'always', 'caused', 'invented', 'discovered']
        for keyword in keywords:
            if keyword in claim.lower():
                facts.append(keyword)
        
        return facts[:5]
    
    def _analyze_paper_alignment(self, claim: str, paper: Dict) -> str:
        """Analyze if paper supports or refutes claim"""
        
        claim_lower = claim.lower()
        title_lower = paper.get('title', '').lower()
        abstract_lower = paper.get('abstract', '').lower() if paper.get('abstract') else ''
        
        contradiction_words = ['no evidence', 'does not', 'failed to', 'unable to', 'no significant', 
                              'myth', 'debunk', 'false', 'incorrect', 'contrary']
        
        support_words = ['confirms', 'demonstrates', 'shows', 'proves', 'evidence for', 'supports',
                         'significant', 'effective', 'successful']
        
        text_to_check = title_lower + ' ' + abstract_lower
        
        has_contradiction = any(word in text_to_check for word in contradiction_words)
        has_support = any(word in text_to_check for word in support_words)
        
        if has_contradiction and not has_support:
            return 'false'
        elif has_support and not has_contradiction:
            return 'true'
        else:
            return 'mixed'
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims with rate limiting"""
        results = []
        
        for idx, claim in enumerate(claims):
            result = self.check_claim(claim)
            results.append(result)
            
            if idx < len(claims) - 1:
                time.sleep(Config.FACT_CHECK_RATE_LIMIT_DELAY)
        
        return results
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> float:
        """Calculate overall credibility score based on fact checks"""
        if not fact_checks:
            return 50.0
        
        verdict_scores = {
            'true': 100,
            'mostly_true': 80,
            'mixed': 50,
            'mostly_false': 20,
            'false': 0,
            'unverified': 50
        }
        
        total_score = 0
        total_weight = 0
        
        for check in fact_checks:
            verdict = check.get('verdict', 'unverified').lower().replace(' ', '_')
            confidence = check.get('confidence', 50) / 100
            
            base_score = verdict_scores.get(verdict, 50)
            weighted_score = base_score * confidence
            
            total_score += weighted_score
            total_weight += confidence
        
        if total_weight > 0:
            credibility = total_score / total_weight
        else:
            credibility = 50.0
        
        return round(credibility, 1)
