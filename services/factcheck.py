"""
Enhanced Fact-Checking Module with Nuanced Interpretation
Includes unclear, misleading verdicts and interpretive analysis
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time

logger = logging.getLogger(__name__)

class EnhancedFactChecker:
    """Enhanced fact checker with nuanced interpretation and AI analysis"""
    
    def __init__(self, config):
        self.google_api_key = config.GOOGLE_FACTCHECK_API_KEY
        self.openai_api_key = config.OPENAI_API_KEY
        self.fred_api_key = config.FRED_API_KEY
        
        # Enhanced verdict options
        self.verdict_options = [
            'true',
            'mostly_true',
            'mixed',
            'unclear',  # NEW: For ambiguous claims
            'misleading',  # NEW: For technically true but deceptive
            'lacks_context',
            'mostly_false',
            'false',
            'unverified',
            'opinion'
        ]
        
        # Enhanced configuration
        self.enable_interpretive_analysis = True
        self.enable_context_comparison = True
        self.enable_nuance_detection = True
        
        # Conversational patterns to filter
        self.conversational_patterns = [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)",
            r"^(thank you|thanks|appreciate)",
            r"^it'?s (good|nice|great) to (see|be)",
            r"^(i'?m |we'?re )(glad|happy|pleased|excited)",
            r"^(welcome|congratulations)",
            r"^(how are you|how'?s everyone)",
            r"^(please|let me|allow me)",
            r"^(um|uh|er|ah|oh|well)",
        ]
        
        # Immigration data for comparison
        self.immigration_data = {
            'border_encounters_2024': 2475669,
            'border_encounters_2023': 2475669,
            'border_encounters_2022': 2378944,
            'border_encounters_2021': 1734686,
            'border_encounters_2020': 458088,
            'ice_arrests_2024': 170590,
            'criminal_arrests_2024': 108790,
            'removals_2024': 271484,  # Removals and returns
        }
        
        # Track similar claims for consistency
        self.claim_comparison_cache = {}
    
    def check_claims_batch(self, claims: List[str], source: str = None) -> List[Dict]:
        """Check claims with nuanced interpretation and consistency checking"""
        if not claims:
            return []
        
        # Step 1: Filter conversational content
        filtered_claims = self._filter_conversational_claims(claims)
        
        # Step 2: Group similar claims for consistency
        claim_groups = self._group_similar_claims(filtered_claims)
        
        # Step 3: Check claims with context awareness
        results = []
        
        for i, claim in enumerate(filtered_claims):
            logger.info(f"Checking claim {i+1}/{len(filtered_claims)}: {claim[:80]}...")
            
            # Try comprehensive check
            try:
                result = self._check_claim_comprehensive(claim)
                results.append(result)
            except Exception as e:
                logger.error(f"Error checking claim: {str(e)}")
                results.append({
                    'claim': claim,
                    'verdict': 'error',
                    'confidence': 0,
                    'explanation': f'Error during fact-check: {str(e)}',
                    'sources': []
                })
            
            # Rate limiting
            time.sleep(0.5)
        
        # Step 4: Ensure consistency among similar claims
        results = self._ensure_consistency(results, claim_groups)
        
        return results
    
    def _extract_temporal_context(self, claim: str) -> Dict:
        """Extract temporal context from claim"""
        temporal_info = {}
        
        # Check for year references
        year_match = re.search(r'\b(20\d{2})\b', claim)
        if year_match:
            year = int(year_match.group(1))
            temporal_info['year'] = year
            
            # Check if referring to partial year
            current_year = datetime.now().year
            if year == current_year:
                temporal_info['partial_year'] = True
                temporal_info['current_date'] = datetime.now().strftime('%B %d, %Y')
            
            # Check for specific time references
            if re.search(r'(so far|thus far|to date|as of|through)', claim, re.IGNORECASE):
                temporal_info['partial_period'] = True
        
        # Check for relative time references
        if re.search(r'(last|previous|past) (year|month|week)', claim, re.IGNORECASE):
            temporal_info['relative_time'] = True
        
        return temporal_info
    
    def _check_patterns(self, claim: str) -> Optional[Dict]:
        """Check for known patterns of misinformation"""
        claim_lower = claim.lower()
        
        # Common false patterns
        false_patterns = [
            ('million illegal', 'billion illegal'),  # Number inflation
            ('crime is down 90%', 'crime decreased 90%'),  # Extreme statistics
            ('never said', "didn't say"),  # Denial patterns - fixed quote
        ]
        
        for pattern, alt in false_patterns:
            if pattern in claim_lower:
                return {
                    'found': True,
                    'claim': claim,
                    'verdict': 'false',
                    'confidence': 75,
                    'explanation': f'This claim contains exaggerated or false information commonly seen in misinformation',
                    'sources': ['Pattern Analysis'],
                    'api_response': False
                }
        
        # Vague attribution patterns
        vague_patterns = ['some people say', 'many believe', 'everyone knows', 'they say']
        if any(pattern in claim_lower for pattern in vague_patterns):
            return {
                'found': True,
                'claim': claim,
                'verdict': 'lacks_context',
                'confidence': 60,
                'explanation': 'This claim uses vague attribution without specific sources.',
                'interpretation': 'The speaker is making a general assertion without specific evidence',
                'source': 'Pattern Analysis',
                'api_response': False
            }
        
        # Absolute statements
        if re.search(r'\b(never|always|all|none|every)\b', claim_lower):
            return {
                'found': True,
                'claim': claim,
                'verdict': 'lacks_context',
                'confidence': 70,
                'explanation': 'Absolute claims rarely account for all exceptions and edge cases.',
                'source': 'Pattern Analysis',
                'api_response': False
            }
        
        return None
    
    def _filter_conversational_claims(self, claims: List[str]) -> List[str]:
        """Filter out conversational/greeting content"""
        filtered = []
        
        for claim in claims:
            claim_lower = claim.lower().strip()
            is_conversational = any(
                re.match(pattern, claim_lower) 
                for pattern in self.conversational_patterns
            )
            
            if is_conversational:
                logger.info(f"Filtered conversational claim: {claim[:50]}...")
                continue
            
            filtered.append(claim)
        
        return filtered
    
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
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Check claim using Google Fact Check API"""
        try:
            if not self.google_api_key:
                return {'found': False}
            
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim,
                'pageSize': 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Process first relevant claim
                    for claim_review in data['claims']:
                        if claim_review.get('claimReview'):
                            review = claim_review['claimReview'][0]
                            
                            verdict = self._normalize_verdict(review.get('textualRating', 'unverified'))
                            
                            return {
                                'found': True,
                                'verdict': verdict,
                                'confidence': 85,
                                'explanation': review.get('title', ''),
                                'sources': [review.get('publisher', {}).get('name', 'Unknown')],
                                'api_response': True
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {str(e)}")
            return {'found': False}
    
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
    
    def _check_with_ai(self, claim: str, context: Dict = None) -> Optional[Dict]:
        """Use AI to analyze claim validity"""
        try:
            if not self.openai_api_key:
                return None
                
            # Try new OpenAI API format first
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                
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
                
                response = client.chat.completions.create(
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
                
            except Exception:
                # Fallback to old API format
                import openai
                openai.api_key = self.openai_api_key
                
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
            
            # Parse the result regardless of which API version was used
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
    
    def _check_claim_comprehensive(self, claim: str) -> Dict:
        """Comprehensive claim checking with multiple methods"""
        result = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': '',
            'sources': [],
            'api_response': False
        }
        
        # Extract temporal context
        temporal_info = self._extract_temporal_context(claim)
        
        # Try Google Fact Check API first
        if self.google_api_key:
            google_result = self._check_google_factcheck(claim)
            if google_result.get('found'):
                result.update(google_result)
                return result
        
        # Try pattern-based checking
        pattern_result = self._check_patterns(claim)
        if pattern_result:
            result.update(pattern_result)
            return result
        
        # Try AI-based checking if available
        if self.openai_api_key:
            ai_result = self._check_with_ai(claim, {'temporal': temporal_info})
            if ai_result:
                result.update(ai_result)
                return result
        
        # Default response
        result['explanation'] = 'Unable to verify this claim with available sources'
        if temporal_info.get('partial_year'):
            result['temporal_note'] = f"Note: {temporal_info['year']} data may be incomplete"
        
        return result
    
    def _ensure_consistency(self, results: List[Dict], claim_groups: Dict[str, List[str]]) -> List[Dict]:
        """Ensure similar claims get consistent verdicts"""
        # Map claims to their results
        claim_to_result = {r['claim']: r for r in results}
        
        # Check each group
        for group_key, similar_claims in claim_groups.items():
            if len(similar_claims) <= 1:
                continue
            
            # Get all results for this group
            group_results = [claim_to_result.get(c) for c in similar_claims if c in claim_to_result]
            
            if len(group_results) <= 1:
                continue
            
            # Check if verdicts are inconsistent
            verdicts = [r['verdict'] for r in group_results if r]
            if len(set(verdicts)) > 1:
                # Inconsistent verdicts for similar claims
                logger.warning(f"Inconsistent verdicts for similar claims: {verdicts}")
                
                # Reconcile verdicts
                reconciled_verdict = self._reconcile_verdicts(group_results)
                
                # Update all results in group
                for result in group_results:
                    if result:
                        result['verdict'] = reconciled_verdict
                        result['consistency_note'] = "Verdict adjusted for consistency with similar claims"
        
        return results
    
    def _reconcile_verdicts(self, results: List[Dict]) -> str:
        """Reconcile different verdicts for similar claims"""
        verdicts = [r['verdict'] for r in results if r]
        confidences = [r.get('confidence', 50) for r in results if r]
        
        # If any are unclear, all should be unclear
        if 'unclear' in verdicts:
            return 'unclear'
        
        # If mix of true/false, use mixed
        if ('true' in verdicts or 'mostly_true' in verdicts) and \
           ('false' in verdicts or 'mostly_false' in verdicts):
            return 'mixed'
        
        # Otherwise, use highest confidence verdict
        if confidences:
            max_conf_idx = confidences.index(max(confidences))
            return verdicts[max_conf_idx]
        
        return 'unverified'

# Main FactChecker class
class FactChecker(EnhancedFactChecker):
    """Main FactChecker class with all enhancements"""
    
    def __init__(self, config):
        """Initialize FactChecker with configuration"""
        super().__init__(config)
        
    def check_claims(self, claims: List[str], context: Dict = None) -> List[Dict]:
        """Check multiple claims and return results
        
        Args:
            claims: List of claim strings to check
            context: Optional context dictionary with metadata
            
        Returns:
            List of fact check results with verdicts and explanations
        """
        # Validate input
        if not claims:
            return []
            
        # Extract source from context if provided
        source = None
        if context and isinstance(context, dict):
            source = context.get('source')
            
        # Use the comprehensive batch checking method
        return self.check_claims_batch(claims, source=source)
