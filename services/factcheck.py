"""
Enhanced Fact Checking Service - Main Module
Coordinates fact-checking using multiple sources and enhanced verdicts
"""
import os
import time
import logging
from typing import List, Dict, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from config import Config

logger = logging.getLogger(__name__)

class FactChecker:
    """Main fact-checking coordinator with enhanced features"""
    
    def __init__(self):
        # Validate setup
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate that the fact checker is properly configured"""
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            logger.warning("Google Fact Check API key not configured - using demo mode")
        
        active_apis = []
        if Config.GOOGLE_FACTCHECK_API_KEY:
            active_apis.append("Google Fact Check")
        
        if active_apis:
            logger.info(f"Fact checker initialized with APIs: {', '.join(active_apis)}")
        else:
            logger.info("Fact checker running in demo mode without APIs")
    
    def batch_check(self, claims: List[str]) -> List[Dict]:
        """Check multiple claims - handles both API and demo modes"""
        results = []
        
        # If no API keys, use demo responses
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            logger.info("Using demo fact-checking responses")
            return self._generate_demo_results(claims)
        
        # Otherwise use real API checking
        for i, claim in enumerate(claims):
            try:
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
        """Check a single claim"""
        # Demo mode if no API keys
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            return self._generate_demo_result(claim)
        
        # Real API checking would go here
        # For now, return unverified
        return self._create_unverified_response(claim, "API implementation pending")
    
    def calculate_credibility(self, fact_checks: List[Dict]) -> int:
        """Calculate overall credibility score from fact check results"""
        if not fact_checks:
            return 50
        
        scores = {
            'true': 100,
            'mostly_true': 75,
            'mixed': 50,
            'misleading': 30,
            'lacks_context': 40,
            'unsubstantiated': 20,
            'mostly_false': 25,
            'false': 0,
            'unverified': 50
        }
        
        total_score = 0
        count = 0
        
        for check in fact_checks:
            verdict = check.get('verdict', 'unverified').lower()
            score = scores.get(verdict, 50)
            total_score += score
            count += 1
        
        return int(total_score / count) if count > 0 else 50
    
    def _generate_demo_results(self, claims: List[str]) -> List[Dict]:
        """Generate demo results for testing without API keys"""
        demo_verdicts = ['true', 'mostly_true', 'mixed', 'false', 'unverified']
        results = []
        
        for i, claim in enumerate(claims):
            # Vary verdicts for demo
            verdict = demo_verdicts[i % len(demo_verdicts)]
            
            # Check for enhanced context
            confidence = 65 + (i % 30)
            publisher = 'Demo Fact Checker'
            
            # Generate appropriate demo response
            if 'percent' in claim.lower() or '%' in claim:
                explanation = "Statistical claim would be verified against official data sources"
            elif any(word in claim.lower() for word in ['first', 'largest', 'most', 'best']):
                explanation = "Superlative claim would be checked against historical records"
            else:
                explanation = "This claim would be fact-checked using multiple sources"
            
            results.append({
                'claim': claim,
                'verdict': verdict,
                'confidence': 65 + (i % 30),  # Vary confidence
                'explanation': f"[DEMO MODE] {explanation}",
                'sources': ['Demo Source'],
                'publisher': 'Demo Fact Checker',
                'url': '',
                'api_response': False
            })
        
        return results
    
    def _generate_demo_result(self, claim: str) -> Dict:
        """Generate a single demo result"""
        # Simple heuristic for demo verdicts
        claim_lower = claim.lower()
        
        if any(word in claim_lower for word in ['always', 'never', 'all', 'none']):
            verdict = 'mostly_false'
            explanation = "Absolute claims are rarely completely true"
        elif 'percent' in claim_lower or '%' in claim_lower:
            verdict = 'unverified'
            explanation = "Statistical claims require verification from official sources"
        else:
            verdict = 'mixed'
            explanation = "This claim contains elements that need verification"
        
        return {
            'claim': claim,
            'verdict': verdict,
            'confidence': 50,
            'explanation': f"[DEMO MODE] {explanation}",
            'sources': ['Demo Analysis'],
            'publisher': 'Demo Mode',
            'url': '',
            'api_response': False
        }
    
    def _create_unverified_response(self, claim: str, reason: str) -> Dict:
        """Create response for unverified claims"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': f"? UNVERIFIED: {reason}",
            'sources': [],
            'publisher': 'N/A',
            'url': '',
            'api_response': False
        }
    
    def _create_error_result(self, claim: str) -> Dict:
        """Create result for errors"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'Error during fact-checking',
            'sources': [],
            'publisher': 'Error',
            'url': '',
            'api_response': False
        }
