"""
Enhanced Fact-Checking Service - Complete Rewrite
Focuses on actual verification of claims rather than opinion-based categorization
"""
import re
import logging
import requests
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
from urllib.parse import quote
import time

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
    }
}

class EnhancedFactChecker:
    """Fact checker that actually verifies claims"""
    
    def __init__(self, config):
        self.config = config
        self.api_keys = {
            'openai': getattr(config, 'OPENAI_API_KEY', None),
            'google': getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None),
            'news': getattr(config, 'NEWS_API_KEY', None),
            'wolfram': getattr(config, 'WOLFRAM_ALPHA_API_KEY', None),
            'scraperapi': getattr(config, 'SCRAPERAPI_KEY', None),
        }
        
        # Initialize OpenAI
        self.openai_client = None
        if self.api_keys['openai']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.api_keys['openai'])
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
        
        # Extract proper nouns (people, places, organizations)
        # Use AI to extract if available
        if self.openai_client:
            entities = self._extract_entities_with_ai(claim)
            elements.extend(entities)
        
        # Extract specific factual claims
        factual_indicators = [
            r'was (?:born|founded|created|established) (?:in|on)',
            r'won (?:the|a)',
            r'(?:is|was|are|were) (?:the|a)',
            r'(?:has|have|had) (?:\d+|a|an|the)',
            r'(?:sold|earned|made|generated) (?:\$?[\d,]+)',
        ]
        
        for pattern in factual_indicators:
            if re.search(pattern, claim, re.IGNORECASE):
                elements.append({
                    'type': 'factual_claim',
                    'value': claim,
                    'pattern': pattern
                })
        
        return elements
    
    def _extract_entities_with_ai(self, claim: str) -> List[Dict]:
        """Use AI to extract named entities"""
        try:
            prompt = f"""Extract all verifiable entities from this claim:
"{claim}"

Return as JSON array with format:
[{{"type": "person|place|organization|event", "name": "...", "context": "..."}}]

Only include entities that can be fact-checked. Be specific."""

            response = self.openai_client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "Extract entities for fact-checking. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            entities = json.loads(result)
            return [{'type': 'entity', 'subtype': e['type'], 'value': e['name'], 'context': e.get('context', claim)} 
                   for e in entities]
            
        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            return []
    
    def _verify_elements(self, elements: List[Dict], full_claim: str) -> List[Dict]:
        """Verify each extracted element"""
        results = []
        
        for element in elements:
            if element['type'] == 'date':
                result = self._verify_date(element, full_claim)
            elif element['type'] == 'statistic':
                result = self._verify_statistic(element, full_claim)
            elif element['type'] == 'entity':
                result = self._verify_entity(element, full_claim)
            elif element['type'] == 'factual_claim':
                result = self._verify_factual_claim(element)
            else:
                continue
            
            if result:
                results.append(result)
        
        # Also check with Google Fact Check API if available
        if self.api_keys['google']:
            google_result = self._check_google_factcheck(full_claim)
            if google_result:
                results.append(google_result)
        
        # Web search for additional verification
        if self.api_keys['scraperapi']:
            web_result = self._verify_with_web_search(full_claim)
            if web_result:
                results.append(web_result)
        
        return results
    
    def _verify_date(self, element: Dict, claim: str) -> Optional[Dict]:
        """Verify date-related claims"""
        try:
            # Use AI to verify if date is accurate in context
            if self.openai_client:
                prompt = f"""Verify if this date is accurate:
Claim: "{claim}"
Date mentioned: {element['value']}

If you can verify this with your knowledge, respond with:
VERIFIED: [TRUE/FALSE]
CORRECT_INFO: [What is actually correct]
CONFIDENCE: [0-100]
EXPLANATION: [Brief explanation]"""

                response = self.openai_client.chat.completions.create(
                    model='gpt-3.5-turbo',
                    messages=[
                        {"role": "system", "content": "Verify dates accurately."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=200
                )
                
                result = response.choices[0].message.content.strip()
                if 'VERIFIED: TRUE' in result:
                    return {
                        'element': element['value'],
                        'verified': True,
                        'explanation': self._extract_explanation(result),
                        'confidence': self._extract_confidence(result)
                    }
                elif 'VERIFIED: FALSE' in result:
                    correct = re.search(r'CORRECT_INFO: (.+?)(?:\n|$)', result)
                    return {
                        'element': element['value'],
                        'verified': False,
                        'correct_info': correct.group(1) if correct else 'Unknown',
                        'explanation': self._extract_explanation(result),
                        'confidence': self._extract_confidence(result)
                    }
        except Exception as e:
            logger.error(f"Date verification error: {e}")
        
        return None
    
    def _verify_statistic(self, element: Dict, claim: str) -> Optional[Dict]:
        """Verify numerical claims"""
        try:
            # Clean the number
            value = element['value']
            
            # Use AI to verify
            if self.openai_client:
                prompt = f"""Verify this statistical claim:
Claim: "{claim}"
Number mentioned: {value}

Check if this number is accurate. If you know the correct figure, provide it.

VERIFIED: [TRUE/FALSE/CANNOT_VERIFY]
CORRECT_VALUE: [Actual value if known]
CONFIDENCE: [0-100]
SOURCE: [Where this can be verified]
EXPLANATION: [Brief explanation]"""

                response = self.openai_client.chat.completions.create(
                    model='gpt-3.5-turbo',
                    messages=[
                        {"role": "system", "content": "Verify statistics with known facts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=200
                )
                
                result = response.choices[0].message.content.strip()
                return self._parse_verification_result(result, element)
                
        except Exception as e:
            logger.error(f"Statistic verification error: {e}")
        
        return None
    
    def _verify_entity(self, element: Dict, claim: str) -> Optional[Dict]:
        """Verify claims about people, places, organizations"""
        try:
            entity_name = element['value']
            entity_type = element.get('subtype', 'entity')
            
            # First try web search for current info
            if self.api_keys['scraperapi']:
                search_query = f"{entity_name} {claim.replace(entity_name, '')}"
                web_result = self._search_and_verify(search_query, claim)
                if web_result:
                    return web_result
            
            # Use AI knowledge
            if self.openai_client:
                prompt = f"""Verify this claim about {entity_type} "{entity_name}":
"{claim}"

Based on your knowledge, is this claim accurate?

VERIFIED: [TRUE/FALSE/PARTIALLY_TRUE/CANNOT_VERIFY]
ISSUES: [List any inaccuracies]
CORRECT_INFO: [What is actually true]
CONFIDENCE: [0-100]
EXPLANATION: [Detailed explanation]"""

                response = self.openai_client.chat.completions.create(
                    model='gpt-4' if 'gpt-4' in str(self.config.OPENAI_MODEL) else 'gpt-3.5-turbo',
                    messages=[
                        {"role": "system", "content": "Verify claims about entities accurately."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=300
                )
                
                return self._parse_verification_result(response.choices[0].message.content.strip(), element)
                
        except Exception as e:
            logger.error(f"Entity verification error: {e}")
        
        return None
    
    def _verify_factual_claim(self, element: Dict) -> Optional[Dict]:
        """Verify general factual claims"""
        claim = element['value']
        
        # Try multiple verification methods
        results = []
        
        # 1. Google Fact Check
        if self.api_keys['google']:
            google_result = self._check_google_factcheck(claim)
            if google_result:
                results.append(google_result)
        
        # 2. Web search
        if self.api_keys['scraperapi']:
            web_result = self._verify_with_web_search(claim)
            if web_result:
                results.append(web_result)
        
        # 3. AI verification
        if self.openai_client:
            ai_result = self._verify_with_ai(claim)
            if ai_result:
                results.append(ai_result)
        
        # Combine results
        if results:
            # If any source says definitively false, it's false
            if any(r.get('verified') is False for r in results):
                false_results = [r for r in results if r.get('verified') is False]
                return false_results[0]
            
            # If all say true, it's true
            if all(r.get('verified') is True for r in results):
                return results[0]
            
            # Mixed results
            return {
                'element': claim,
                'verified': 'mixed',
                'results': results,
                'explanation': 'Multiple sources provide conflicting information',
                'confidence': 50
            }
        
        return None
    
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
            search_queries = [
                f'"{claim}" fact check',
                f'"{claim}" false OR true OR verified',
                f'{claim} debunked OR confirmed'
            ]
            
            for query in search_queries:
                result = self._search_and_verify(query, claim)
                if result:
                    return result
                    
        except Exception as e:
            logger.error(f"Web search verification error: {e}")
        
        return None
    
    def _search_and_verify(self, query: str, original_claim: str) -> Optional[Dict]:
        """Search and analyze results"""
        try:
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
                            'element': original_claim,
                            'verified': False,
                            'explanation': ' | '.join(explanations),
                            'source': 'Web Search',
                            'confidence': min(70 + (is_false * 10), 90)
                        }
                    elif is_true > is_false:
                        return {
                            'element': original_claim,
                            'verified': True,
                            'explanation': ' | '.join(explanations),
                            'source': 'Web Search',
                            'confidence': min(70 + (is_true * 10), 90)
                        }
                        
        except Exception as e:
            logger.error(f"Search and verify error: {e}")
        
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
CONFIDENCE: [0-100]
ISSUES: [Any inaccuracies or misleading elements]"""

            response = self.openai_client.chat.completions.create(
                model='gpt-4' if 'gpt-4' in str(self.config.OPENAI_MODEL) else 'gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a strict fact-checker. Only verify claims you are certain about."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=300
            )
            
            return self._parse_verification_result(response.choices[0].message.content.strip(), {'value': claim})
            
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
        mixed_results = sum(1 for r in verification_results if r.get('verified') == 'mixed')
        cannot_verify = sum(1 for r in verification_results if r.get('verified') == 'cannot_verify')
        
        # Collect all explanations
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
        elif mixed_results > 0:
            verdict = 'partially_accurate'
            explanation = "Mixed evidence found. " + " ".join(explanations)
        else:
            verdict = 'unverifiable'
            explanation = "Insufficient evidence to verify. " + " ".join(explanations)
        
        return self._create_verdict(
            verdict,
            explanation,
            confidence=int(avg_confidence),
            sources=list(set(sources))
        )
    
    def _is_pure_opinion(self, claim: str) -> bool:
        """Check if claim is pure opinion"""
        opinion_indicators = [
            r'\b(i think|i believe|i feel|in my opinion|seems to me|appears to be)\b',
            r'\b(probably|maybe|perhaps|possibly|likely)\b',
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
    
    def _extract_explanation(self, result: str) -> str:
        """Extract explanation from result"""
        match = re.search(r'EXPLANATION: (.+?)(?:\n|$)', result, re.DOTALL)
        return match.group(1).strip() if match else "No explanation provided"
    
    def _extract_confidence(self, result: str) -> int:
        """Extract confidence from result"""
        match = re.search(r'CONFIDENCE: (\d+)', result)
        return int(match.group(1)) if match else 50
    
    def _parse_verification_result(self, result: str, element: Dict) -> Optional[Dict]:
        """Parse AI verification result"""
        try:
            verdict_match = re.search(r'VERDICT: (\w+)', result)
            if not verdict_match:
                return None
            
            verdict = verdict_match.group(1).upper()
            
            if verdict == 'TRUE':
                verified = True
            elif verdict == 'FALSE':
                verified = False
            elif verdict == 'CANNOT_VERIFY':
                verified = 'cannot_verify'
            else:
                verified = 'mixed'
            
            return {
                'element': element['value'],
                'verified': verified,
                'explanation': self._extract_explanation(result),
                'confidence': self._extract_confidence(result),
                'source': 'AI Analysis'
            }
            
        except Exception as e:
            logger.error(f"Parse verification error: {e}")
            return None
    
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

# Wrapper for compatibility
class FactChecker(EnhancedFactChecker):
    """Wrapper to maintain compatibility with existing code"""
    pass
