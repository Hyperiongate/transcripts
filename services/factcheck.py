# Main FactChecker class
class FactChecker(EnhancedFactChecker):
    """Main FactChecker class with all enhancements"""
    
    def __init__(self, config):
        """Initialize FactChecker with configuration"""
        super().__init__(config)
        
    def check_claims(self, claims: List[str], context: Dict = None) -> List[Dict]:
        """Check multiple claims and return results"""
        # Use the batch method which is more comprehensive
        return self.check_claims_batch(claims, source=context.get('source') if context else None)"""
Fact Checking Service
"""
import logging
import requests
from typing import List, Dict, Optional
import time
import openai
from datetime import datetime

logger = logging.getLogger(__name__)

class FactChecker:
    """Enhanced fact checker with multiple verification methods"""
    
    def __init__(self, config):
        """Initialize fact checker with configuration"""
        self.config = config
        self.google_api_key = config.GOOGLE_FACTCHECK_API_KEY
        self.openai_api_key = config.OPENAI_API_KEY
        self.fact_check_timeout = config.FACT_CHECK_TIMEOUT
        
        # Initialize OpenAI if API key is available
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        # Cache for API responses
        self.cache = {}
        
    def check_claims(self, claims: List[str], context: Dict = None) -> List[Dict]:
        """Check multiple claims and return results"""
        results = []
        
        for i, claim in enumerate(claims):
            logger.info(f"Checking claim {i+1}/{len(claims)}: {claim[:100]}...")
            
            try:
                # Check claim with timeout
                result = self._check_claim_comprehensive(claim, context)
                results.append(result)
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error checking claim: {str(e)}")
                results.append({
                    'claim': claim,
                    'verdict': 'error',
                    'confidence': 0,
                    'explanation': f'Error during fact-check: {str(e)}',
                    'sources': []
                })
        
        return results
    
    def check_claims_batch(self, claims: List[str], source: str = None) -> List[Dict]:
        """Batch check claims with context awareness"""
        # Extract context from claims
        context = self._extract_context(claims, source)
        
        # Group similar claims
        claim_groups = self._group_similar_claims(claims)
        
        # Check claims
        results = []
        for claim in claims:
            result = self._check_claim_comprehensive(claim, context)
            results.append(result)
        
        # Ensure consistency for similar claims
        results = self._ensure_consistency(results, claim_groups)
        
        return results
    
    def _check_claim_comprehensive(self, claim: str, context: Dict = None) -> Dict:
        """Comprehensive claim checking with multiple methods"""
        result = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': '',
            'sources': [],
            'api_response': False
        }
        
        # Try Google Fact Check API first
        if self.google_api_key:
            google_result = self._check_google_factcheck(claim)
            if google_result.get('found'):
                result.update(google_result)
                result['api_response'] = True
                return result
        
        # Try pattern-based checking
        pattern_result = self._check_patterns(claim, context)
        if pattern_result:
            result.update(pattern_result)
            return result
        
        # Try AI-based checking if available
        if self.openai_api_key:
            ai_result = self._check_with_ai(claim, context)
            if ai_result:
                result.update(ai_result)
                return result
        
        # Default response
        result['explanation'] = 'Unable to verify this claim with available sources'
        return result
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Check claim using Google Fact Check API"""
        try:
            # Check cache first
            cache_key = f"google_{claim[:50]}"
            if cache_key in self.cache:
                return self.cache[cache_key]
            
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim,
                'pageSize': 10
            }
            
            response = requests.get(url, params=params, timeout=self.fact_check_timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Process first relevant claim
                    for claim_review in data['claims']:
                        if claim_review.get('claimReview'):
                            review = claim_review['claimReview'][0]
                            
                            verdict = self._normalize_verdict(review.get('textualRating', 'unverified'))
                            
                            result = {
                                'found': True,
                                'verdict': verdict,
                                'confidence': 85,
                                'explanation': review.get('title', ''),
                                'sources': [review.get('publisher', {}).get('name', 'Unknown')]
                            }
                            
                            # Cache result
                            self.cache[cache_key] = result
                            return result
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {str(e)}")
            return {'found': False}
    
    def _check_patterns(self, claim: str, context: Dict = None) -> Optional[Dict]:
        """Check for known patterns and false claims"""
        claim_lower = claim.lower()
        
        # Common false patterns
        false_patterns = [
            ('million illegal', 'billion illegal'),  # Number inflation
            ('crime is down 90%', 'crime decreased 90%'),  # Extreme statistics
            ('never said', 'didn't say'),  # Denial patterns
        ]
        
        for pattern, alt in false_patterns:
            if pattern in claim_lower:
                return {
                    'verdict': 'false',
                    'confidence': 75,
                    'explanation': f'This claim contains exaggerated or false information commonly seen in misinformation',
                    'sources': ['Pattern Analysis']
                }
        
        # Check temporal context
        if context and context.get('date'):
            # Extract date references
            if '2025' in claim and context['date'].year < 2025:
                return {
                    'verdict': 'impossible',
                    'confidence': 100,
                    'explanation': 'This claim references future events that haven\'t occurred yet',
                    'sources': ['Temporal Analysis']
                }
        
        return None
    
    def _check_with_ai(self, claim: str, context: Dict = None) -> Optional[Dict]:
        """Use AI to analyze claim validity"""
        try:
            # Build context prompt
            context_info = ""
            if context:
                if context.get('speaker'):
                    context_info += f"Speaker: {context['speaker']}\n"
                if context.get('date'):
                    context_info += f"Date: {context['date']}\n"
                if context.get('topic'):
                    context_info += f"Topic: {context['topic']}\n"
            
            prompt = f"""Analyze this factual claim for accuracy. Be objective and cite-based.

{context_info}
Claim: "{claim}"

Provide:
1. Verdict: true/mostly_true/mixed/mostly_false/false/unverified
2. Confidence: 0-100
3. Brief explanation
4. Key issue if any

Format: VERDICT|CONFIDENCE|EXPLANATION|ISSUE"""
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a fact-checker. Be accurate and objective."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            # Parse response
            result_text = response.choices[0].message.content.strip()
            parts = result_text.split('|')
            
            if len(parts) >= 3:
                return {
                    'verdict': self._normalize_verdict(parts[0].strip()),
                    'confidence': int(parts[1].strip()),
                    'explanation': parts[2].strip(),
                    'sources': ['AI Analysis'],
                    'key_issue': parts[3].strip() if len(parts) > 3 else None
                }
                
        except Exception as e:
            logger.error(f"AI checking error: {str(e)}")
        
        return None
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict strings to standard format"""
        verdict_lower = verdict.lower().strip()
        
        mapping = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mostly-true': 'mostly_true',
            'half true': 'mixed',
            'half-true': 'mixed',
            'mixed': 'mixed',
            'mostly false': 'mostly_false',
            'mostly-false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'incorrect': 'false',
            'misleading': 'misleading',
            'unverified': 'unverified',
            'unproven': 'unverified',
            'unknown': 'unverified'
        }
        
        return mapping.get(verdict_lower, 'unverified')
    
    def _extract_context(self, claims: List[str], source: str = None) -> Dict:
        """Extract context from claims"""
        context = {}
        
        # Extract potential speaker from claims
        speaker_keywords = ['said', 'says', 'claimed', 'stated', 'according to']
        for claim in claims:
            for keyword in speaker_keywords:
                if keyword in claim.lower():
                    # Simple extraction (can be improved)
                    parts = claim.split(keyword)
                    if len(parts) > 1:
                        potential_speaker = parts[0].strip().rstrip(',')
                        if len(potential_speaker) < 50:  # Reasonable name length
                            context['speaker'] = potential_speaker
                            break
        
        # Add source info
        if source:
            context['source'] = source
        
        # Add current date
        context['date'] = datetime.now()
        
        return context
    
    def _group_similar_claims(self, claims: List[str]) -> Dict[str, List[str]]:
        """Group similar claims together"""
        groups = {}
        
        # Simple grouping by key terms
        for claim in claims:
            # Extract key terms (numbers, main nouns)
            key_terms = []
            words = claim.lower().split()
            
            for word in words:
                # Keep numbers
                if any(char.isdigit() for char in word):
                    key_terms.append(word)
                # Keep significant words
                elif len(word) > 5 and word not in ['about', 'around', 'approximately']:
                    key_terms.append(word)
            
            # Create group key
            group_key = ' '.join(sorted(key_terms[:3]))
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(claim)
        
        return groups
    
    def _ensure_consistency(self, results: List[Dict], claim_groups: Dict[str, List[str]]) -> List[Dict]:
        """Ensure similar claims get consistent verdicts"""
        # Implementation depends on business logic
        # For now, return results as-is
        return results
