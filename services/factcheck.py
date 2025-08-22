"""
Enhanced Fact-Checking Service - Verification-focused approach
Replaces opinion-based categorization with actual fact verification
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Redesigned verdict system focused on verifiability
VERDICT_CATEGORIES = {
    'verified_true': {
        'label': 'Verified True',
        'icon': '✅',
        'color': '#10b981',
        'score': 100,
        'description': 'Claim verified as factually accurate through multiple sources'
    },
    'verified_false': {
        'label': 'Verified False',
        'icon': '❌',
        'color': '#ef4444',
        'score': 0,
        'description': 'Claim verified as factually incorrect through reliable sources'
    },
    'partially_accurate': {
        'label': 'Partially Accurate',
        'icon': '⚠️',
        'color': '#f59e0b',
        'score': 50,
        'description': 'Some elements true, others false or misleading'
    },
    'unverifiable': {
        'label': 'Unverifiable',
        'icon': '❓',
        'color': '#6b7280',
        'score': None,
        'description': 'Cannot be verified with available information'
    },
    'opinion': {
        'label': 'Opinion',
        'icon': '💭',
        'color': '#8b5cf6',
        'score': None,
        'description': 'Subjective statement, not a factual claim'
    },
    # Keep some old verdicts for compatibility during transition
    'needs_context': {
        'label': 'Unverifiable',
        'icon': '❓',
        'color': '#6b7280',
        'score': None,
        'description': 'Cannot be verified with available information'
    }
}

class FactChecker:
    """Fact checker that actually verifies claims"""
    
    def __init__(self, config):
        self.config = config
        self.api_keys = {
            'openai': getattr(config, 'OPENAI_API_KEY', None),
            'google': getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None),
            'news': getattr(config, 'NEWS_API_KEY', None),
            'scraperapi': getattr(config, 'SCRAPERAPI_KEY', None),
        }
        
        # Initialize OpenAI
        self.openai_client = None
        if self.api_keys['openai']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.api_keys['openai'])
                logger.info("OpenAI initialized for fact-checking")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Check a claim and return verification result"""
        try:
            # Clean and validate claim
            claim = claim.strip()
            if len(claim.split()) < 3:
                return self._create_verdict('unverifiable', 'Statement too short to verify')
            
            # Check if pure opinion
            if self._is_pure_opinion(claim):
                return self._create_verdict('opinion', 'This is a subjective opinion')
            
            # Extract verifiable elements
            verifiable_elements = self._extract_verifiable_elements(claim)
            if not verifiable_elements:
                # Try web search anyway
                web_result = self._verify_with_web_search(claim)
                if web_result and web_result.get('verified') is not None:
                    return self._create_verdict_from_result(web_result, claim)
                return self._create_verdict('unverifiable', 'No verifiable facts found in claim')
            
            # Run verification
            verification_results = self._verify_elements(verifiable_elements, claim)
            
            # Synthesize results
            return self._synthesize_results(claim, verification_results)
            
        except Exception as e:
            logger.error(f"Error in fact check: {e}")
            return self._create_verdict('unverifiable', f'Error during verification: {str(e)}')
    
    def _extract_verifiable_elements(self, claim: str) -> List[Dict]:
        """Extract specific facts that can be verified"""
        elements = []
        
        # Extract dates
        date_patterns = [
            r'\b(\d{4})\b',  # Years
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, claim, re.IGNORECASE)
            for match in matches:
                elements.append({
                    'type': 'date',
                    'value': match,
                    'context': claim
                })
        
        # Extract numbers/statistics
        number_patterns = [
            r'\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|thousand))?',
            r'\b\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|thousand|percent|%))\b',
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\b',
        ]
        for pattern in number_patterns:
            matches = re.findall(pattern, claim, re.IGNORECASE)
            for match in matches:
                elements.append({
                    'type': 'statistic',
                    'value': match,
                    'context': claim
                })
        
        # Extract factual claims about events/people
        if any(word in claim.lower() for word in ['born', 'founded', 'created', 'won', 'sold', 'earned']):
            elements.append({
                'type': 'factual_claim',
                'value': claim,
                'pattern': 'event_claim'
            })
        
        return elements
    
    def _verify_elements(self, elements: List[Dict], full_claim: str) -> List[Dict]:
        """Verify each extracted element"""
        results = []
        
        # Always try Google Fact Check first
        if self.api_keys['google']:
            google_result = self._check_google_factcheck(full_claim)
            if google_result:
                results.append(google_result)
        
        # Try web search
        if self.api_keys['scraperapi']:
            web_result = self._verify_with_web_search(full_claim)
            if web_result:
                results.append(web_result)
        
        # If no results yet, try AI
        if not results and self.openai_client:
            ai_result = self._verify_with_ai(full_claim)
            if ai_result:
                results.append(ai_result)
        
        return results
    
    def _check_google_factcheck(self, claim: str) -> Optional[Dict]:
        """Use Google Fact Check API"""
        if not self.api_keys['google']:
            return None
        
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.api_keys['google'],
                'query': claim,
                'languageCode': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('claims'):
                    claim_data = data['claims'][0]
                    review = claim_data.get('claimReview', [{}])[0]
                    rating = review.get('textualRating', '')
                    
                    # Map rating to our system
                    if any(word in rating.lower() for word in ['true', 'correct', 'accurate']):
                        verified = True
                    elif any(word in rating.lower() for word in ['false', 'incorrect', 'wrong']):
                        verified = False
                    else:
                        verified = 'mixed'
                    
                    return {
                        'element': claim,
                        'verified': verified,
                        'explanation': review.get('title', rating),
                        'source': review.get('publisher', {}).get('name', 'Fact Checker'),
                        'confidence': 85
                    }
                    
        except Exception as e:
            logger.error(f"Google Fact Check error: {e}")
        
        return None
    
    def _verify_with_web_search(self, claim: str) -> Optional[Dict]:
        """Search web for verification"""
        if not self.api_keys['scraperapi']:
            return None
        
        try:
            # Search for fact-checking of this claim
            query = f'"{claim}" fact check OR false OR true OR verified'
            
            url = "https://api.scraperapi.com/structured/google/search"
            params = {
                'api_key': self.api_keys['scraperapi'],
                'query': query,
                'num': 5
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get('organic_results', [])
                
                # Analyze results
                verification_found = False
                is_true = 0
                is_false = 0
                explanations = []
                
                for result in results:
                    title = result.get('title', '').lower()
                    snippet = result.get('snippet', '').lower()
                    content = f"{title} {snippet}"
                    
                    # Look for verification indicators
                    if any(word in content for word in ['fact check', 'verified', 'debunked', 'confirmed']):
                        verification_found = True
                        
                        if any(word in content for word in ['false', 'incorrect', 'debunked', 'myth', 'no evidence']):
                            is_false += 1
                            explanations.append(f"{result.get('title')}: Indicates false")
                        elif any(word in content for word in ['true', 'correct', 'confirmed', 'accurate', 'verified']):
                            is_true += 1
                            explanations.append(f"{result.get('title')}: Indicates true")
                
                if verification_found:
                    if is_false > is_true:
                        return {
                            'element': claim,
                            'verified': False,
                            'explanation': ' | '.join(explanations),
                            'source': 'Web Search',
                            'confidence': min(70 + (is_false * 10), 90)
                        }
                    elif is_true > is_false:
                        return {
                            'element': claim,
                            'verified': True,
                            'explanation': ' | '.join(explanations),
                            'source': 'Web Search',
                            'confidence': min(70 + (is_true * 10), 90)
                        }
                        
        except Exception as e:
            logger.error(f"Web search error: {e}")
        
        return None
    
    def _verify_with_ai(self, claim: str) -> Optional[Dict]:
        """Use AI for verification as last resort"""
        if not self.openai_client:
            return None
        
        try:
            prompt = f"""You are a fact-checker with knowledge up to early 2024.

Verify this specific claim: "{claim}"

Rules:
1. Only say TRUE if you are certain this is accurate based on your knowledge
2. Only say FALSE if you are certain this is inaccurate
3. Say CANNOT_VERIFY if you're unsure or lack information
4. Provide specific evidence for your verdict

Format:
VERDICT: [TRUE/FALSE/CANNOT_VERIFY]
EVIDENCE: [Specific facts that support or refute the claim]
CONFIDENCE: [0-100]"""

            response = self.openai_client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a strict fact-checker. Only verify claims you are certain about."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse response
            verdict_match = re.search(r'VERDICT: (\w+)', result)
            confidence_match = re.search(r'CONFIDENCE: (\d+)', result)
            evidence_match = re.search(r'EVIDENCE: (.+?)(?:\n|$)', result, re.DOTALL)
            
            if verdict_match:
                verdict = verdict_match.group(1).upper()
                confidence = int(confidence_match.group(1)) if confidence_match else 50
                evidence = evidence_match.group(1).strip() if evidence_match else "No evidence provided"
                
                if verdict == 'TRUE':
                    verified = True
                elif verdict == 'FALSE':
                    verified = False
                else:
                    return None
                
                return {
                    'element': claim,
                    'verified': verified,
                    'explanation': evidence,
                    'confidence': confidence,
                    'source': 'AI Analysis'
                }
            
        except Exception as e:
            logger.error(f"AI verification error: {e}")
        
        return None
    
    def _synthesize_results(self, claim: str, verification_results: List[Dict]) -> Dict:
        """Synthesize all verification results into final verdict"""
        if not verification_results:
            return self._create_verdict('unverifiable', 'Could not verify claim with available sources')
        
        # Count verification outcomes
        verified_true = sum(1 for r in verification_results if r.get('verified') is True)
        verified_false = sum(1 for r in verification_results if r.get('verified') is False)
        
        # Collect all explanations and sources
        explanations = []
        sources = []
        total_confidence = 0
        confidence_count = 0
        
        for result in verification_results:
            if result.get('explanation'):
                explanations.append(result['explanation'])
            if result.get('source'):
                sources.append(result['source'])
            if result.get('confidence'):
                total_confidence += result['confidence']
                confidence_count += 1
        
        avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 50
        
        # Determine final verdict
        if verified_false > 0 and verified_true == 0:
            verdict = 'verified_false'
            explanation = "Claim verified as false. " + " ".join(explanations)
        elif verified_true > 0 and verified_false == 0:
            verdict = 'verified_true'
            explanation = "Claim verified as true. " + " ".join(explanations)
        elif verified_true > 0 and verified_false > 0:
            verdict = 'partially_accurate'
            explanation = "Claim contains both true and false elements. " + " ".join(explanations)
        else:
            verdict = 'unverifiable'
            explanation = "Insufficient evidence to verify. " + " ".join(explanations)
        
        return self._create_verdict(
            verdict,
            explanation,
            confidence=int(avg_confidence),
            sources=list(set(sources))
        )
    
    def _create_verdict_from_result(self, result: Dict, claim: str) -> Dict:
        """Create verdict from a single result"""
        if result.get('verified') is True:
            verdict = 'verified_true'
        elif result.get('verified') is False:
            verdict = 'verified_false'
        else:
            verdict = 'unverifiable'
        
        return self._create_verdict(
            verdict,
            result.get('explanation', 'No explanation provided'),
            confidence=result.get('confidence', 50),
            sources=[result.get('source', 'Unknown')]
        )
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if claim is pure opinion"""
        opinion_indicators = [
            r'\b(i think|i believe|i feel|in my opinion|seems to me|appears to be)\b',
            r'\b(should|ought to|must|need to)\b',
            r'\b(best|worst|greatest|terrible|awesome|horrible)\b'
        ]
        
        claim_lower = claim.lower()
        
        # Check for opinion phrases
        for pattern in opinion_indicators:
            if re.search(pattern, claim_lower):
                # But check if it's quoting someone else's opinion as a fact
                if not re.search(r'(said|says|stated|claimed|according to)', claim_lower):
                    return True
        
        return False
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 50, sources: List[str] = None) -> Dict:
        """Create standardized verdict"""
        return {
            'verdict': verdict,
            'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['unverifiable']),
            'explanation': explanation,
            'confidence': confidence,
            'sources': sources or [],
            'timestamp': datetime.now().isoformat()
        }
    
    # Keep compatibility methods
    def check_claim_comprehensive(self, claim: str, context: Dict[str, Any]) -> Dict:
        """Compatibility method"""
        return self.check_claim_with_verdict(claim, context)
    
    def get_speaker_context(self, speaker_name: str) -> Dict[str, Any]:
        """Compatibility method"""
        return {
            'criminal_record': None,
            'fraud_history': None,
            'fact_check_history': {
                'total_claims': 0,
                'false_claims': 0,
                'accuracy_rate': 0
            }
        }
    
    def generate_summary(self, fact_checks: List[Dict]) -> str:
        """Generate summary of fact checks"""
        if not fact_checks:
            return "No claims were fact-checked."
        
        total = len(fact_checks)
        verdict_counts = {}
        
        for fc in fact_checks:
            verdict = fc.get('verdict', 'unverifiable')
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        summary = f"Analyzed {total} claims:\n"
        for verdict, count in verdict_counts.items():
            verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['unverifiable'])
            summary += f"- {verdict_info['label']}: {count}\n"
        
        return summary
        
