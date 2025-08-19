"""
Enhanced Fact-Checking Module with Parallel Processing
Optimized for speed with concurrent API calls
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time
from functools import partial

logger = logging.getLogger(__name__)

class FactChecker:
    """Optimized fact checker with parallel processing"""
    
    def __init__(self, config):
        self.google_api_key = config.GOOGLE_FACTCHECK_API_KEY
        self.openai_api_key = config.OPENAI_API_KEY
        
        # Performance settings
        self.max_workers = 5  # Number of parallel workers
        self.api_timeout = 5  # Reduced timeout per API call
        self.batch_size = 5  # Process claims in batches
        
        # Cache for API responses
        self.cache = {}
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
    
    def check_claims(self, claims: List[str], source: str = None) -> List[Dict]:
        """Check multiple claims in parallel for maximum speed"""
        if not claims:
            return []
        
        results = []
        total_claims = len(claims)
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all claims for checking
            future_to_claim = {}
            
            for i, claim in enumerate(claims):
                # Check cache first
                cache_key = self._get_cache_key(claim)
                if cache_key in self.cache:
                    results.append(self.cache[cache_key])
                    logger.info(f"Claim {i+1}/{total_claims} - Using cached result")
                    continue
                
                # Submit for checking
                future = executor.submit(self._check_single_claim_fast, claim, i, total_claims)
                future_to_claim[future] = (claim, i)
            
            # Collect results as they complete
            for future in as_completed(future_to_claim):
                claim, index = future_to_claim[future]
                try:
                    result = future.result(timeout=self.api_timeout + 2)
                    results.append(result)
                    
                    # Cache the result
                    cache_key = self._get_cache_key(claim)
                    self.cache[cache_key] = result
                    
                except TimeoutError:
                    logger.warning(f"Timeout checking claim: {claim[:50]}...")
                    results.append(self._create_timeout_result(claim))
                except Exception as e:
                    logger.error(f"Error checking claim: {e}")
                    results.append(self._create_error_result(claim))
        
        # Sort results back to original order
        results.sort(key=lambda x: claims.index(x['claim']))
        
        return results
    
    def _check_single_claim_fast(self, claim: str, index: int, total: int) -> Dict:
        """Fast single claim check with fallback options"""
        logger.info(f"Checking claim {index+1}/{total}: {claim[:80]}...")
        
        # Try Google Fact Check API first (fastest)
        if self.google_api_key:
            result = self._check_google_fast(claim)
            if result.get('found'):
                return result
        
        # Try quick pattern matching
        pattern_result = self._quick_pattern_check(claim)
        if pattern_result:
            return pattern_result
        
        # Use AI only if enabled and as last resort
        if self.openai_client and index < 10:  # Limit AI calls for speed
            ai_result = self._check_with_ai_fast(claim)
            if ai_result:
                return ai_result
        
        # Default result
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'Unable to verify with available sources',
            'sources': [],
            'processing_time': 0
        }
    
    def _check_google_fast(self, claim: str) -> Dict:
        """Optimized Google Fact Check API call"""
        start_time = time.time()
        
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],  # Limit query length
                'pageSize': 5  # Reduced for speed
            }
            
            response = requests.get(url, params=params, timeout=self.api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    claim_review = data['claims'][0]
                    if claim_review.get('claimReview'):
                        review = claim_review['claimReview'][0]
                        
                        processing_time = time.time() - start_time
                        
                        return {
                            'found': True,
                            'claim': claim,
                            'verdict': self._normalize_verdict(review.get('textualRating', 'unverified')),
                            'confidence': 85,
                            'explanation': review.get('title', ''),
                            'sources': [review.get('publisher', {}).get('name', 'Unknown')],
                            'url': review.get('url', ''),
                            'processing_time': processing_time
                        }
            
            return {'found': False}
            
        except requests.Timeout:
            logger.warning(f"Google API timeout for claim: {claim[:50]}...")
            return {'found': False}
        except Exception as e:
            logger.error(f"Google API error: {e}")
            return {'found': False}
    
    def _quick_pattern_check(self, claim: str) -> Optional[Dict]:
        """Quick pattern-based fact checking"""
        claim_lower = claim.lower()
        
        # Quick checks for obviously false claims
        false_patterns = [
            (r'election was stolen', 'false', 'Multiple courts and investigations found no evidence of widespread fraud'),
            (r'vaccine.*cause.*autism', 'false', 'Extensively studied and debunked by medical research'),
            (r'climate change is a hoax', 'false', 'Scientific consensus confirms climate change'),
            (r'earth is flat', 'false', 'Scientifically proven false'),
        ]
        
        for pattern, verdict, explanation in false_patterns:
            if re.search(pattern, claim_lower):
                return {
                    'claim': claim,
                    'verdict': verdict,
                    'confidence': 95,
                    'explanation': explanation,
                    'sources': ['Scientific Consensus'],
                    'processing_time': 0.01
                }
        
        # Quick checks for verifiable statistics
        stat_patterns = [
            (r'unemployment.*(\d+\.?\d*)\s*%', 'Check current unemployment rate'),
            (r'inflation.*(\d+\.?\d*)\s*%', 'Check current inflation rate'),
            (r'(\d+)\s*(?:million|billion).*(?:jobs|employed)', 'Check employment statistics'),
        ]
        
        for pattern, note in stat_patterns:
            if re.search(pattern, claim_lower):
                return {
                    'claim': claim,
                    'verdict': 'unverified',
                    'confidence': 50,
                    'explanation': f'Statistical claim - {note}',
                    'sources': ['Requires Current Data'],
                    'processing_time': 0.01
                }
        
        return None
    
    def _check_with_ai_fast(self, claim: str) -> Optional[Dict]:
        """Fast AI-based fact checking"""
        if not self.openai_client:
            return None
        
        try:
            start_time = time.time()
            
            # Use a concise prompt for speed
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a fact-checker. Respond in format: VERDICT|CONFIDENCE|BRIEF_EXPLANATION"},
                    {"role": "user", "content": f"Fact-check: {claim[:200]}"}
                ],
                temperature=0.3,
                max_tokens=100,
                timeout=self.api_timeout
            )
            
            result_text = response.choices[0].message.content.strip()
            parts = result_text.split('|')
            
            if len(parts) >= 3:
                processing_time = time.time() - start_time
                
                return {
                    'claim': claim,
                    'verdict': self._normalize_verdict(parts[0].strip()),
                    'confidence': int(parts[1].strip()) if parts[1].strip().isdigit() else 70,
                    'explanation': parts[2].strip(),
                    'sources': ['AI Analysis'],
                    'processing_time': processing_time
                }
                
        except Exception as e:
            logger.error(f"AI checking error: {e}")
        
        return None
    
    def _normalize_verdict(self, rating: str) -> str:
        """Normalize verdict ratings"""
        rating_lower = rating.lower()
        
        # Map various rating formats to standard verdicts
        verdict_map = {
            'true': ['true', 'correct', 'accurate', 'verified', 'fact'],
            'mostly_true': ['mostly true', 'mostly correct', 'largely accurate', 'mostly accurate'],
            'mixed': ['mixed', 'mixture', 'half true', 'partially true', 'partially correct'],
            'mostly_false': ['mostly false', 'largely false', 'mostly incorrect'],
            'false': ['false', 'incorrect', 'wrong', 'inaccurate', 'debunked', 'fake'],
            'unverified': ['unverified', 'unproven', 'no evidence', 'cannot verify', 'unknown']
        }
        
        for verdict, keywords in verdict_map.items():
            if any(keyword in rating_lower for keyword in keywords):
                return verdict
        
        return 'unverified'
    
    def _get_cache_key(self, claim: str) -> str:
        """Generate cache key for claim"""
        # Simple hash of normalized claim
        return claim.lower().strip()[:100]
    
    def _create_timeout_result(self, claim: str) -> Dict:
        """Create result for timeout cases"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'Fact-checking timed out',
            'sources': [],
            'processing_time': self.api_timeout
        }
    
    def _create_error_result(self, claim: str) -> Dict:
        """Create result for error cases"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'Error during fact-checking',
            'sources': [],
            'processing_time': 0
        }
