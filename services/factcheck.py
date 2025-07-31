"""
Enhanced Fact Checking Service - Truth Verification Focus
"""
import os
import time
import logging
import requests
import asyncio
import aiohttp
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Fact checker focused on verifying truth of claims, not attribution"""
    
    def __init__(self):
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.news_api_key = getattr(Config, 'NEWS_API_KEY', None)
        self.scraperapi_key = getattr(Config, 'SCRAPERAPI_KEY', None)
        
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
        
        # First, identify what type of claim this is
        claim_type = self._identify_claim_type(claim)
        
        # Run appropriate verification based on claim type
        if claim_type == 'statistical':
            return await self._verify_statistical_claim(claim)
        elif claim_type == 'scientific':
            return await self._verify_scientific_claim(claim)
        elif claim_type == 'historical':
            return await self._verify_historical_claim(claim)
        elif claim_type == 'current_event':
            return await self._verify_current_event(claim)
        else:
            # General verification for other claims
            return await self._verify_general_claim(claim)
    
    def _identify_claim_type(self, claim: str) -> str:
        """Identify what type of claim we're dealing with"""
        claim_lower = claim.lower()
        
        # Statistical claims contain numbers, percentages, or comparisons
        if any(pattern in claim for pattern in [r'\d+%', r'\d+ percent', 'million', 'billion', 'increased', 'decreased']):
            return 'statistical'
        
        # Scientific claims
        elif any(word in claim_lower for word in ['causes', 'cures', 'prevents', 'scientifically', 'proven', 'study shows']):
            return 'scientific'
        
        # Historical claims
        elif any(word in claim_lower for word in ['first', 'invented', 'discovered', 'founded', 'historical', 'originally']):
            return 'historical'
        
        # Current events
        elif any(word in claim_lower for word in ['currently', 'now', 'today', 'recently', 'just', 'breaking']):
            return 'current_event'
        
        return 'general'
    
    async def _verify_statistical_claim(self, claim: str) -> Dict:
        """Verify claims containing statistics or numbers"""
        
        # Extract the specific statistic
        numbers = re.findall(r'\d+\.?\d*', claim)
        
        # Try multiple verification approaches
        results = await asyncio.gather(
            self._check_google_factcheck(claim),
            self._verify_against_official_sources(claim),
            self._check_fact_checker_sites(claim),
            return_exceptions=True
        )
        
        # Process results focusing on TRUTH
        valid_results = [r for r in results if isinstance(r, dict) and r.get('found')]
        
        if not valid_results:
            return self._create_unverified_response(claim, "Cannot verify statistical claim without access to authoritative data sources")
        
        # Synthesize based on agreement about TRUTH
        return self._synthesize_truth_verdict(claim, valid_results)
    
    async def _verify_scientific_claim(self, claim: str) -> Dict:
        """Verify scientific or medical claims"""
        
        # For scientific claims, prioritize authoritative sources
        results = await asyncio.gather(
            self._check_google_factcheck(claim),
            self._check_scientific_consensus(claim),
            self._check_fact_checker_sites(claim),
            return_exceptions=True
        )
        
        valid_results = [r for r in results if isinstance(r, dict) and r.get('found')]
        
        if not valid_results:
            return self._create_unverified_response(claim, "Scientific claim requires peer-reviewed sources for verification")
        
        return self._synthesize_truth_verdict(claim, valid_results)
    
    async def _verify_general_claim(self, claim: str) -> Dict:
        """General verification for any claim type"""
        
        results = await asyncio.gather(
            self._check_google_factcheck(claim),
            self._check_fact_checker_sites(claim),
            self._cross_reference_sources(claim),
            return_exceptions=True
        )
        
        valid_results = [r for r in results if isinstance(r, dict) and r.get('found')]
        
        if not valid_results:
            return self._create_unverified_response(claim, "No reliable sources found to verify this claim")
        
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
            
            # Extract the truth verdict, not attribution
            rating = review.get('textualRating', '')
            verdict = self._normalize_truth_verdict(rating)
            
            return {
                'found': True,
                'verdict': verdict,
                'explanation': review.get('title', ''),
                'source': review.get('publisher', {}).get('name', 'Fact Checker'),
                'url': review.get('url', ''),
                'confidence': 85 if verdict != 'unverified' else 40
            }
        return {'found': False}
    
    async def _check_fact_checker_sites(self, claim: str) -> Dict:
        """Check dedicated fact-checking sites for truth verdicts"""
        # Simplified for now - would implement actual scraping
        return {'found': False}
    
    async def _verify_against_official_sources(self, claim: str) -> Dict:
        """Verify against official data sources"""
        # Check for specific topics and route to appropriate sources
        claim_lower = claim.lower()
        
        if 'unemployment' in claim_lower or 'jobs' in claim_lower:
            source = "Bureau of Labor Statistics"
        elif 'covid' in claim_lower or 'vaccine' in claim_lower:
            source = "CDC"
        elif 'climate' in claim_lower or 'temperature' in claim_lower:
            source = "NOAA"
        else:
            return {'found': False}
        
        # In production, would actually query these sources
        # For now, return structured response
        return {
            'found': True,
            'verdict': 'unverified',
            'explanation': f'Requires direct verification from {source}',
            'source': source,
            'confidence': 50
        }
    
    async def _check_scientific_consensus(self, claim: str) -> Dict:
        """Check scientific consensus on claims"""
        # Would implement checks against scientific databases
        return {'found': False}
    
    async def _cross_reference_sources(self, claim: str) -> Dict:
        """Cross-reference multiple reliable sources"""
        if not self.news_api_key:
            return {'found': False}
        
        try:
            # Extract key facts to verify
            key_terms = self._extract_verifiable_facts(claim)
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.news_api_key,
                'q': ' '.join(key_terms),
                'sortBy': 'relevancy',
                'pageSize': 5,
                'language': 'en',
                'domains': 'reuters.com,apnews.com,bbc.com'  # Reliable sources only
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('articles'):
                            # Don't just check if claim was reported, check if it's TRUE
                            return self._analyze_truth_from_sources(claim, data['articles'])
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Cross-reference error: {str(e)}")
            return {'found': False}
    
    def _synthesize_truth_verdict(self, claim: str, results: List[Dict]) -> Dict:
        """Synthesize final verdict focused on TRUTH, not attribution"""
        
        # Collect all verdicts about truth
        verdicts = []
        explanations = []
        sources = []
        
        for result in results:
            verdict = result.get('verdict', 'unverified')
            if verdict != 'unverified':
                verdicts.append({
                    'verdict': verdict,
                    'confidence': result.get('confidence', 50),
                    'source': result.get('source', 'Unknown')
                })
                if result.get('explanation'):
                    explanations.append(f"{result['source']}: {result['explanation']}")
                sources.append(result.get('source', 'Unknown'))
        
        if not verdicts:
            return self._create_unverified_response(claim, "No sources could verify the truthfulness of this claim")
        
        # Determine final verdict based on consensus
        final_verdict = self._calculate_consensus_verdict(verdicts)
        confidence = self._calculate_truth_confidence(verdicts)
        
        # Create clear, justified explanation
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
        
        # Weight verdicts by confidence
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
            confidence = v['confidence'] / 100
            if verdict in verdict_scores:
                verdict_scores[verdict] += confidence
                total_weight += confidence
        
        if total_weight == 0:
            return 'unverified'
        
        # Find dominant verdict
        best_verdict = max(verdict_scores.items(), key=lambda x: x[1])
        
        # If there's strong disagreement, return mixed
        if best_verdict[1] / total_weight < 0.6:
            return 'mixed'
        
        return best_verdict[0]
    
    def _calculate_truth_confidence(self, verdicts: List[Dict]) -> int:
        """Calculate confidence in truth verdict"""
        if not verdicts:
            return 0
        
        # Base confidence on number of sources and agreement
        base_confidence = min(len(verdicts) * 25, 75)
        
        # Check agreement
        verdict_types = [v['verdict'] for v in verdicts]
        unique_verdicts = set(verdict_types)
        
        if len(unique_verdicts) == 1:
            # Full agreement
            agreement_bonus = 20
        elif len(unique_verdicts) == 2:
            # Partial agreement
            agreement_bonus = 10
        else:
            # Disagreement
            agreement_bonus = 0
        
        return min(base_confidence + agreement_bonus, 95)
    
    def _create_truth_explanation(self, verdict: str, explanations: List[str], sources: List[str]) -> str:
        """Create clear explanation of WHY claim is true/false"""
        
        # Start with verdict definition
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
        
        # Add specific evidence
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
        
        # Clear TRUE mappings
        if any(word in rating_lower for word in ['true', 'correct', 'accurate', 'fact', 'confirmed', 'yes']):
            if any(qualifier in rating_lower for qualifier in ['mostly', 'partly', 'largely', 'substantially']):
                return 'mostly_true'
            return 'true'
        
        # Clear FALSE mappings
        elif any(word in rating_lower for word in ['false', 'incorrect', 'wrong', 'fake', 'debunked', 'no']):
            if any(qualifier in rating_lower for qualifier in ['mostly', 'partly', 'largely', 'substantially']):
                return 'mostly_false'
            return 'false'
        
        # MIXED mappings
        elif any(word in rating_lower for word in ['mixed', 'half', 'partially', 'complicated', 'partly true', 'partly false']):
            return 'mixed'
        
        # Everything else is unverified
        else:
            return 'unverified'
    
    def _extract_verifiable_facts(self, claim: str) -> List[str]:
        """Extract specific facts that can be verified"""
        # Remove attribution phrases
        claim = re.sub(r'(according to|says|claims|stated|reported).*?,', '', claim, flags=re.IGNORECASE)
        
        # Extract key factual elements
        facts = []
        
        # Numbers and statistics
        numbers = re.findall(r'\d+\.?\d*%?', claim)
        facts.extend(numbers)
        
        # Proper nouns (people, places, organizations)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', claim)
        facts.extend(proper_nouns)
        
        # Key factual words
        keywords = ['first', 'largest', 'smallest', 'only', 'never', 'always', 'caused', 'invented', 'discovered']
        for keyword in keywords:
            if keyword in claim.lower():
                facts.append(keyword)
        
        return facts[:5]  # Top 5 facts
    
    def _analyze_truth_from_sources(self, claim: str, articles: List[Dict]) -> Dict:
        """Analyze if claim is TRUE based on source content, not just if it was reported"""
        # In production, would analyze article content for factual verification
        # For now, return that verification is needed
        return {
            'found': True,
            'verdict': 'unverified',
            'explanation': f'Found {len(articles)} related articles but need to analyze content for truth verification',
            'source': 'News Analysis',
            'confidence': 40
        }
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims with rate limiting"""
        results = []
        
        for idx, claim in enumerate(claims):
            # Check claim
            result = self.check_claim(claim)
            results.append(result)
            
            # Rate limiting
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
