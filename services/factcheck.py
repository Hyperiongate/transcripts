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
            # Find similar claims
            similar_claims = claim_groups.get(claim, [])
            
            # Check claim with awareness of similar claims
            result = self._check_claim_with_context(claim, similar_claims, source)
            
            # Store for comparison
            self.claim_comparison_cache[claim] = result
            
            results.append(result)
        
        # Step 4: Post-process for consistency
        results = self._ensure_consistency(results, claim_groups)
        
        return results
    
    def _group_similar_claims(self, claims: List[str]) -> Dict[str, List[str]]:
        """Group similar claims together for consistency checking"""
        groups = {}
        
        for i, claim1 in enumerate(claims):
            similar = [claim1]
            
            for j, claim2 in enumerate(claims):
                if i != j and self._are_claims_similar(claim1, claim2):
                    similar.append(claim2)
            
            groups[claim1] = similar
        
        return groups
    
    def _are_claims_similar(self, claim1: str, claim2: str) -> bool:
        """Determine if two claims are similar enough to need consistent verdicts"""
        # Normalize for comparison
        c1_lower = claim1.lower()
        c2_lower = claim2.lower()
        
        # Extract key elements
        c1_numbers = set(re.findall(r'\d+(?:,\d+)?(?:\.\d+)?', claim1))
        c2_numbers = set(re.findall(r'\d+(?:,\d+)?(?:\.\d+)?', claim2))
        
        # Same numbers mentioned?
        if c1_numbers and c2_numbers and c1_numbers == c2_numbers:
            return True
        
        # Similar topic keywords?
        topic_keywords = ['arrest', 'criminal', 'alien', 'border', 'crossing', 'illegal', 'remove', 'deport']
        c1_topics = [kw for kw in topic_keywords if kw in c1_lower]
        c2_topics = [kw for kw in topic_keywords if kw in c2_lower]
        
        # If they share multiple topic keywords and numbers
        if len(set(c1_topics) & set(c2_topics)) >= 2:
            return True
        
        # Check semantic similarity if AI available
        if self.openai_api_key:
            return self._check_semantic_similarity(claim1, claim2)
        
        return False
    
    def _check_semantic_similarity(self, claim1: str, claim2: str) -> bool:
        """Use AI to check if claims are semantically similar"""
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""Are these two claims making essentially the same assertion about the same topic?

Claim 1: "{claim1}"
Claim 2: "{claim2}"

Answer with just 'yes' or 'no'."""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You determine if claims are semantically similar.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0,
                'max_tokens': 10
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=3
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content'].strip().lower()
                return answer == 'yes'
                
        except Exception as e:
            logger.debug(f"Semantic similarity check failed: {str(e)}")
        
        return False
    
    def _check_claim_with_context(self, claim: str, similar_claims: List[str], source: str) -> Dict:
        """Check claim with awareness of similar claims and context"""
        logger.info(f"Checking claim with context: {claim[:80]}...")
        
        # Use AI for interpretive analysis if available
        if self.openai_api_key and self.enable_interpretive_analysis:
            ai_result = self._analyze_claim_with_ai(claim, similar_claims)
            if ai_result and ai_result.get('found'):
                return ai_result
        
        # Fallback to enhanced pattern checking
        return self._check_claim_comprehensive(claim)
    
    def _analyze_claim_with_ai(self, claim: str, similar_claims: List[str]) -> Optional[Dict]:
        """Use AI for nuanced claim analysis"""
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Build context about similar claims
            context = ""
            if len(similar_claims) > 1:
                context = f"\nNote: Similar claims in this transcript include: {'; '.join(similar_claims[:3])}"
            
            prompt = f"""Analyze this claim for fact-checking. Consider what the speaker appears to be trying to say, not just the literal words.

Claim: "{claim}"{context}

Provide your analysis in this exact format:
INTERPRETATION: [What the speaker appears to be claiming]
VERDICT: [Choose ONE: true, mostly_true, mixed, unclear, misleading, lacks_context, mostly_false, false, unverified]
CONFIDENCE: [0-100]
EXPLANATION: [Brief explanation]
KEY_ISSUE: [Main problem if any: ambiguous_wording, missing_context, partial_data, conflicting_data, or none]

Guidelines:
- Use "unclear" when the claim is too ambiguous to verify
- Use "misleading" when technically true but intentionally deceptive
- Consider if they're referring to partial year data (e.g., "in 2025" might mean "so far in 2025")
- Look for what they're trying to communicate, not just literal accuracy"""
            
            data = {
                'model': 'gpt-4' if 'gpt-4' in self.openai_api_key else 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are a nuanced fact-checker who considers context and apparent intent.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 300
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse AI response
                parsed = self._parse_ai_analysis(content, claim)
                if parsed:
                    parsed['ai_interpreted'] = True
                    return parsed
                    
        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
        
        return None
    
    def _parse_ai_analysis(self, ai_response: str, original_claim: str) -> Optional[Dict]:
        """Parse AI analysis response into structured result"""
        try:
            lines = ai_response.strip().split('\n')
            result = {
                'claim': original_claim,
                'found': True,
                'api_response': True,
                'source': 'AI Analysis'
            }
            
            for line in lines:
                if line.startswith('INTERPRETATION:'):
                    result['interpretation'] = line.replace('INTERPRETATION:', '').strip()
                elif line.startswith('VERDICT:'):
                    verdict = line.replace('VERDICT:', '').strip().lower()
                    if verdict in self.verdict_options:
                        result['verdict'] = verdict
                elif line.startswith('CONFIDENCE:'):
                    conf_str = line.replace('CONFIDENCE:', '').strip()
                    result['confidence'] = int(re.findall(r'\d+', conf_str)[0])
                elif line.startswith('EXPLANATION:'):
                    result['explanation'] = line.replace('EXPLANATION:', '').strip()
                elif line.startswith('KEY_ISSUE:'):
                    issue = line.replace('KEY_ISSUE:', '').strip()
                    if issue != 'none':
                        result['key_issue'] = issue
            
            # Ensure all required fields
            if 'verdict' in result and 'explanation' in result:
                return result
                
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
        
        return None
    
    def _ensure_consistency(self, results: List[Dict], claim_groups: Dict[str, List[str]]) -> List[Dict]:
        """Ensure similar claims get consistent verdicts"""
        # Map claims to their results
        claim_to_result = {r['claim']: r for r in results}
        
        # Check each group
        for claim, similar_claims in claim_groups.items():
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
        verdicts = [r['verdict'] for r in results]
        confidences = [r.get('confidence', 50) for r in results]
        
        # If any are unclear, all should be unclear
        if 'unclear' in verdicts:
            return 'unclear'
        
        # If mix of true/false, use mixed
        if ('true' in verdicts or 'mostly_true' in verdicts) and \
           ('false' in verdicts or 'mostly_false' in verdicts):
            return 'mixed'
        
        # Otherwise, use highest confidence verdict
        max_conf_idx = confidences.index(max(confidences))
        return verdicts[max_conf_idx]
    
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
    
    def _check_claim_comprehensive(self, claim: str) -> Dict:
        """Comprehensive claim checking with enhanced patterns"""
        logger.info(f"Checking claim: {claim[:80]}...")
        
        # Extract temporal context
        temporal_info = self._extract_temporal_context(claim)
        
        # Check specific patterns
        
        # 1. Immigration/arrest claims with numbers
        if any(term in claim.lower() for term in ['arrest', 'criminal', 'alien', 'illegal']):
            result = self._check_immigration_arrest_claim(claim, temporal_info)
            if result:
                return result
        
        # 2. Border crossing claims
        if 'border' in claim.lower() or 'crossing' in claim.lower():
            result = self._check_border_claim(claim, temporal_info)
            if result:
                return result
        
        # 3. War/conflict claims
        if any(term in claim.lower() for term in ['war', 'ukraine', 'russia']):
            result = self._check_war_claim(claim)
            if result:
                return result
        
        # 4. Check against known data
        result = self._check_against_known_data(claim)
        if result and result.get('found'):
            return result
        
        # 5. Google Fact Check
        if self.google_api_key:
            google_result = self._check_google_enhanced(claim)
            if google_result['found']:
                return google_result
        
        # 6. Pattern analysis
        pattern_result = self._analyze_claim_patterns(claim)
        if pattern_result['found']:
            return pattern_result
        
        # Default
        return self._create_intelligent_result(claim, temporal_info)
    
    def _check_immigration_arrest_claim(self, claim: str, temporal_info: Dict) -> Optional[Dict]:
        """Check immigration and arrest-related claims with nuance"""
        claim_lower = claim.lower()
        
        # Extract numbers
        numbers = re.findall(r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:thousand|million)?', claim)
        
        # Check for 300,000 or similar
        if any('300' in num for num in numbers):
            # Different contexts for 300,000
            if 'arrest' in claim_lower and ('criminal' in claim_lower or 'alien' in claim_lower):
                
                # Check if it's about removals vs arrests
                if 'remove' in claim_lower or 'deport' in claim_lower:
                    interpretation = "removals and returns of immigrants"
                    actual_number = self.immigration_data.get('removals_2024', 271484)
                    verdict = 'mostly_true' if actual_number > 250000 else 'mostly_false'
                else:
                    interpretation = "arrests of immigrants with criminal records"
                    actual_number = self.immigration_data.get('criminal_arrests_2024', 108790)
                    verdict = 'misleading'  # Using removal numbers for arrests
                
                explanation = (
                    f"This claim appears to refer to {interpretation}. "
                    f"The actual figure for FY2024 was {actual_number:,}. "
                )
                
                if temporal_info.get('partial_year') and '2025' in claim:
                    explanation += "Note: 2025 data is still being collected."
                    verdict = 'unclear' if verdict == 'misleading' else verdict
                
                return {
                    'claim': claim,
                    'verdict': verdict,
                    'confidence': 75,
                    'explanation': explanation,
                    'interpretation': f"The speaker appears to be referring to {interpretation}",
                    'actual_value': f"{actual_number:,}",
                    'source': 'DHS/ICE Statistics',
                    'key_issue': 'ambiguous_terminology' if 'arrest' in claim_lower and actual_number < 200000 else None,
                    'api_response': False
                }
        
        return None
    
    def _check_border_claim(self, claim: str, temporal_info: Dict) -> Optional[Dict]:
        """Check border-related claims with context"""
        claim_lower = claim.lower()
        
        if '90%' in claim and 'down' in claim_lower:
            return {
                'claim': claim,
                'verdict': 'lacks_context',
                'confidence': 80,
                'explanation': (
                    "This claim about a 90% decrease in border crossings requires specific time periods "
                    "for comparison. Border encounters vary significantly by month and year. Without knowing "
                    "the baseline and current periods being compared, this cannot be verified."
                ),
                'interpretation': "The speaker is claiming border crossings have decreased by 90% from some previous level",
                'missing_context': 'Specific time periods for comparison (e.g., compared to which month/year?)',
                'source': 'Pattern Analysis',
                'api_response': False
            }
        
        return None
    
    def _check_war_claim(self, claim: str) -> Optional[Dict]:
        """Check war-related claims with historical context"""
        claim_lower = claim.lower()
        
        if 'ukraine' in claim_lower and any(phrase in claim_lower for phrase in ['war started', 'war began']):
            if 'biden' in claim_lower:
                return {
                    'claim': claim,
                    'verdict': 'mostly_true',
                    'confidence': 85,
                    'explanation': (
                        "While the Russia-Ukraine conflict has roots dating to 2014 with the annexation of Crimea, "
                        "the current full-scale war began on February 24, 2022, during the Biden presidency. "
                        "The speaker appears to be referring to this current phase of the conflict."
                    ),
                    'interpretation': "The speaker is referring to the 2022 full-scale invasion, not the 2014 conflict",
                    'source': 'Historical Timeline',
                    'api_response': False
                }
        
        return None
    
    def _check_against_known_data(self, claim: str) -> Dict:
        """Check claim against known immigration/border data"""
        claim_lower = claim.lower()
        
        # Extract year if mentioned
        year_match = re.search(r'20\d{2}', claim)
        if not year_match:
            return {'found': False}
        
        year = year_match.group()
        
        # Check if we have data for this year
        for data_key, value in self.immigration_data.items():
            if year in data_key:
                # Extract numbers from claim
                numbers = re.findall(r'(\d+(?:,\d+)?(?:\.\d+)?)', claim)
                
                for num_str in numbers:
                    claimed_value = float(num_str.replace(',', ''))
                    
                    # Check if claim mentions millions
                    if 'million' in claim_lower:
                        claimed_value *= 1000000
                    
                    # Compare values (within 20% considered mostly true)
                    if value > 0:
                        difference = abs(claimed_value - value) / value
                        
                        if difference < 0.2:
                            return {
                                'found': True,
                                'claim': claim,
                                'verdict': 'mostly_true' if difference < 0.1 else 'mixed',
                                'confidence': 80,
                                'explanation': f'Close to official data: {value:,}',
                                'source': 'Government Statistics',
                                'api_response': False
                            }
                        elif difference > 0.5:
                            return {
                                'found': True,
                                'claim': claim,
                                'verdict': 'mostly_false' if difference < 1.0 else 'false',
                                'confidence': 80,
                                'explanation': f'Significantly different from official data. Actual: {value:,}',
                                'source': 'Government Statistics',
                                'actual_value': f'{value:,}',
                                'claimed_value': f'{claimed_value:,.0f}',
                                'api_response': False
                            }
        
        return {'found': False}
    
    def _extract_temporal_context(self, claim: str) -> Dict:
        """Extract temporal context from claim"""
        context = {}
        
        # Partial year patterns
        partial_patterns = [
            r'thus far in (\d{4})',
            r'so far in (\d{4})',
            r'to date in (\d{4})',
            r'in (\d{4}) so far',
            r'in (\d{4}) to date',
            r'already in (\d{4})',
            r'in the first .* (?:months?|weeks?|days?) of (\d{4})',
        ]
        
        for pattern in partial_patterns:
            match = re.search(pattern, claim, re.IGNORECASE)
            if match:
                context['partial_year'] = True
                context['year'] = match.group(1)
                context['reference_type'] = 'partial_year'
                break
        
        # Also check for just "in 2025" which might mean partial
        if not context.get('partial_year') and '2025' in claim:
            # If discussing 2025 and we're still in 2025, likely partial
            if datetime.now().year == 2025:
                context['partial_year'] = True
                context['year'] = '2025'
                context['reference_type'] = 'current_year'
        
        return context
    
    def _check_google_enhanced(self, claim: str) -> Dict:
        """Enhanced Google fact check"""
        try:
            params = {
                'key': self.google_api_key,
                'query': claim
            }
            
            response = requests.get(
                'https://factchecktools.googleapis.com/v1alpha1/claims:search',
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Get first result
                    claim_data = data['claims'][0]
                    review = claim_data.get('claimReview', [{}])[0]
                    
                    rating = review.get('textualRating', '').lower()
                    
                    # Enhanced verdict mapping
                    verdict_map = {
                        'true': 'true',
                        'mostly true': 'mostly_true',
                        'mixture': 'mixed',
                        'mostly false': 'mostly_false',
                        'false': 'false',
                        'unproven': 'unverified',
                        'misleading': 'misleading'
                    }
                    
                    return {
                        'found': True,
                        'claim': claim,
                        'verdict': verdict_map.get(rating, 'unverified'),
                        'confidence': 80,
                        'explanation': review.get('title', 'Fact check available'),
                        'source': review.get('publisher', {}).get('name', 'Fact Checker'),
                        'url': review.get('url', ''),
                        'api_response': True
                    }
            
        except Exception as e:
            logger.error(f"Google fact check error: {str(e)}")
        
        return {'found': False}
    
    def _analyze_claim_patterns(self, claim: str) -> Dict:
        """Analyze claim patterns for common issues"""
        claim_lower = claim.lower()
        
        # Vague quantifiers
        if any(term in claim_lower for term in ['many', 'some', 'a lot of', 'numerous']):
            return {
                'found': True,
                'claim': claim,
                'verdict': 'unclear',
                'confidence': 70,
                'explanation': 'This claim uses vague quantifiers that cannot be precisely verified.',
                'interpretation': 'The speaker is making a general assertion without specific numbers',
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
        
        return {'found': False}
    
    def _create_intelligent_result(self, claim: str, temporal_info: Dict = None) -> Dict:
        """Create intelligent result for unmatched claims"""
        result = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 40,
            'explanation': 'Unable to verify this claim with available sources.',
            'source': 'Automated Analysis',
            'api_response': False
        }
        
        # Add temporal context
        if temporal_info and temporal_info.get('partial_year'):
            result['temporal_note'] = f"This appears to reference partial {temporal_info['year']} data"
            result['verdict'] = 'unclear'
            result['explanation'] = (
                f"This claim about {temporal_info['year']} cannot be fully verified as the year is ongoing. "
                "The numbers may represent partial year data."
            )
        
        # Check if it's an opinion
        if any(phrase in claim.lower() for phrase in ['i think', 'i believe', 'in my opinion']):
            result['verdict'] = 'opinion'
            result['explanation'] = 'This is an opinion rather than a verifiable factual claim.'
            result['confidence'] = 90
        
        return result

# Main FactChecker class
class FactChecker(EnhancedFactChecker):
    """Main FactChecker class with all enhancements"""
    pass
