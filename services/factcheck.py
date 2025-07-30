"""
Fact checking service
Verifies claims using Google Fact Check API and other methods
"""
import os
import time
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Fact check claims using multiple sources"""
    
    def __init__(self):
        self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
        self.session = requests.Session()
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        
    def check_claim(self, claim: str) -> Dict:
        """Check a single claim"""
        if self.google_api_key:
            return self._check_with_google_api(claim)
        else:
            return self._generate_mock_result(claim)
    
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
        
        # Count verdicts
        verdict_scores = {
            'true': 100,
            'mostly_true': 80,
            'half_true': 50,
            'mostly_false': 20,
            'false': 0,
            'unverified': 50
        }
        
        total_score = 0
        total_weight = 0
        
        for check in fact_checks:
            verdict = check.get('verdict', 'unverified').lower().replace(' ', '_')
            confidence = check.get('confidence', 50) / 100
            
            # Get base score for verdict
            base_score = verdict_scores.get(verdict, 50)
            
            # Weight by confidence
            weighted_score = base_score * confidence
            
            total_score += weighted_score
            total_weight += confidence
        
        # Calculate weighted average
        if total_weight > 0:
            credibility = total_score / total_weight
        else:
            credibility = 50.0
        
        return round(credibility, 1)
    
    def _check_with_google_api(self, claim: str) -> Dict:
        """Check claim using Google Fact Check API"""
        try:
            params = {
                'key': self.google_api_key,
                'query': claim[:200],  # Limit query length
                'languageCode': 'en'
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Process first relevant result
                    claim_data = data['claims'][0]
                    
                    # Extract review information
                    if 'claimReview' in claim_data and claim_data['claimReview']:
                        review = claim_data['claimReview'][0]
                        
                        verdict = self._normalize_verdict(review.get('textualRating', 'Unverified'))
                        
                        return {
                            'claim': claim,
                            'verdict': verdict,
                            'confidence': self._calculate_confidence(review),
                            'explanation': review.get('title', 'No explanation available'),
                            'publisher': review.get('publisher', {}).get('name', 'Unknown'),
                            'url': review.get('url', ''),
                            'sources': [review.get('publisher', {}).get('name', 'Google Fact Check')],
                            'api_response': True
                        }
                
                # No results found
                return self._generate_mock_result(claim, no_data=True)
                
            else:
                logger.warning(f"Google API error: {response.status_code}")
                return self._generate_mock_result(claim)
                
        except Exception as e:
            logger.error(f"Fact check API error: {str(e)}")
            return self._generate_mock_result(claim)
    
    def _normalize_verdict(self, rating: str) -> str:
        """Normalize verdict ratings to standard format"""
        rating_lower = rating.lower()
        
        # Map common ratings to standard verdicts
        if any(word in rating_lower for word in ['true', 'correct', 'accurate']):
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_true'
            return 'true'
        
        elif any(word in rating_lower for word in ['false', 'incorrect', 'inaccurate', 'fake']):
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_false'
            return 'false'
        
        elif any(word in rating_lower for word in ['mixed', 'half', 'partially']):
            return 'half_true'
        
        else:
            return 'unverified'
    
    def _calculate_confidence(self, review: Dict) -> int:
        """Calculate confidence score based on review data"""
        confidence = 50  # Base confidence
        
        # Increase confidence if from known fact-checker
        known_checkers = ['Snopes', 'FactCheck.org', 'PolitiFact', 'Reuters', 'AP']
        publisher = review.get('publisher', {}).get('name', '')
        
        if any(checker in publisher for checker in known_checkers):
            confidence += 20
        
        # Increase confidence if has URL
        if review.get('url'):
            confidence += 10
        
        # Increase confidence if has detailed rating
        if review.get('textualRating') and len(review.get('textualRating', '')) > 5:
            confidence += 10
        
        return min(confidence, 90)
    
    def _generate_mock_result(self, claim: str, no_data: bool = False) -> Dict:
        """Generate mock result when API is not available"""
        # Simple heuristic-based mock verdict
        claim_lower = claim.lower()
        
        # Check for obviously false patterns
        if any(word in claim_lower for word in ['earth is flat', 'vaccines cause autism', '5g causes']):
            verdict = 'false'
            confidence = 85
            explanation = 'This claim has been thoroughly debunked by scientific consensus'
        
        # Check for likely true patterns
        elif any(word in claim_lower for word in ['earth revolves', 'water boils at 100', 'gravity']):
            verdict = 'true'
            confidence = 90
            explanation = 'This is a well-established scientific fact'
        
        # Check for statistical claims
        elif any(char in claim for char in ['%', 'percent', 'million', 'billion']):
            verdict = 'unverified'
            confidence = 40
            explanation = 'Statistical claim requires specific source verification'
        
        else:
            verdict = 'unverified'
            confidence = 30
            explanation = 'Unable to verify this claim without additional sources' if no_data else 'Fact checking service unavailable'
        
        return {
            'claim': claim,
            'verdict': verdict,
            'confidence': confidence,
            'explanation': explanation,
            'publisher': 'Mock Fact Checker' if not self.google_api_key else 'Limited Search',
            'url': '',
            'sources': ['Heuristic Analysis'],
            'api_response': False
        }
