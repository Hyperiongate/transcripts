"""
Enhanced Fact-Checking Module with AI Filtering and Improved Accuracy
Addresses temporal context, source verification, and conversational filtering
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time

# Import other modules
from .political_topics import PoliticalTopicsChecker
from .speaker_history import SpeakerHistoryTracker

logger = logging.getLogger(__name__)

class EnhancedFactChecker:
    """Enhanced fact checker with AI filtering and temporal awareness"""
    
    def __init__(self, config, temporal_processor=None):
        self.google_api_key = config.GOOGLE_FACTCHECK_API_KEY
        self.openai_api_key = config.OPENAI_API_KEY
        self.fred_api_key = config.FRED_API_KEY
        self.temporal_processor = temporal_processor
        
        # Initialize sub-checkers
        self.political_checker = PoliticalTopicsChecker()
        self.speaker_tracker = SpeakerHistoryTracker()
        
        # Enhanced configuration
        self.enable_ai_filtering = True
        self.enable_source_verification = True
        self.enable_temporal_intelligence = True
        
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
        
        # Updated war/conflict understanding
        self.war_timeline = {
            'ukraine_russia': {
                '2014': 'Russian annexation of Crimea and Eastern Ukraine conflict',
                '2022': 'Full-scale Russian invasion of Ukraine',
                'biden_era': 'February 24, 2022 - Full invasion began under Biden presidency',
                'context': 'While Russia-Ukraine tensions date to 2014, the current war began in 2022'
            }
        }
        
        # Netanyahu statement tracking
        self.recent_statements = {}
        self.statement_cache_duration = timedelta(hours=24)
        
    def check_claims_batch(self, claims: List[str], source: str = None) -> List[Dict]:
        """Main entry point with enhanced AI filtering"""
        if not claims:
            return []
        
        # Step 1: Filter out conversational content
        filtered_claims = self._filter_conversational_claims(claims)
        
        # Step 2: Apply temporal context if available
        if self.temporal_processor and source:
            temporal_claims = []
            for claim in filtered_claims:
                processed = self.temporal_processor.process_claim_with_context(claim, source)
                temporal_claims.append(processed)
            filtered_claims = temporal_claims
        
        # Step 3: Check claims with enhanced logic
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_claim = {
                executor.submit(self._check_claim_comprehensive, claim): claim 
                for claim in filtered_claims
            }
            
            for future in as_completed(future_to_claim, timeout=30):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    claim = future_to_claim[future]
                    logger.error(f"Error checking claim '{claim[:50]}...': {str(e)}")
                    results.append(self._create_error_result(claim))
        
        return results
    
    def _filter_conversational_claims(self, claims: List[str]) -> List[str]:
        """Filter out conversational/greeting content using AI when available"""
        filtered = []
        
        for claim in claims:
            # Quick pattern check first
            claim_lower = claim.lower().strip()
            is_conversational = any(
                re.match(pattern, claim_lower) 
                for pattern in self.conversational_patterns
            )
            
            if is_conversational:
                logger.info(f"Filtered conversational claim: {claim[:50]}...")
                continue
            
            # AI check for ambiguous cases if enabled
            if self.enable_ai_filtering and self.openai_api_key and len(claim) < 100:
                if self._is_conversational_ai(claim):
                    logger.info(f"AI filtered conversational claim: {claim[:50]}...")
                    continue
            
            filtered.append(claim)
        
        return filtered
    
    def _is_conversational_ai(self, claim: str) -> bool:
        """Use AI to determine if a claim is conversational/non-factual"""
        if not self.openai_api_key:
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""Is this a factual claim that can be fact-checked, or is it conversational/greeting/opinion?
            
Text: "{claim}"

Answer with ONLY 'factual' or 'conversational'. No explanation needed."""
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You categorize text as factual claims or conversational content.'},
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
                return answer == 'conversational'
                
        except Exception as e:
            logger.debug(f"AI conversational check failed: {str(e)}")
        
        return False
    
    def _check_claim_comprehensive(self, claim: str) -> Dict:
        """Enhanced claim checking with all improvements"""
        logger.info(f"Checking claim: {claim[:80]}...")
        
        # Extract temporal context
        temporal_info = self._extract_temporal_context(claim)
        
        # Handle specific accuracy issues
        
        # 1. "Thus far in 2025" interpretation
        if temporal_info.get('partial_year') and '2025' in claim:
            claim_adjusted = self._adjust_partial_year_claim(claim)
        else:
            claim_adjusted = claim
        
        # 2. Netanyahu statement verification
        if 'netanyahu' in claim.lower() and any(word in claim.lower() for word in ['said', 'stated', 'claimed']):
            source_result = self._verify_statement_source(claim, 'Netanyahu')
            if source_result:
                return source_result
        
        # 3. Ukraine war context
        if 'ukraine' in claim.lower() and 'war' in claim.lower():
            war_result = self._check_ukraine_war_claim(claim)
            if war_result:
                return war_result
        
        # 4. Percentage interpretation fix
        if '90%' in claim and 'border' in claim.lower():
            border_result = self._check_border_percentage_claim(claim)
            if border_result:
                return border_result
        
        # 5. Check with actual numbers from political topics
        political_result = self.political_checker.check_claim(claim_adjusted)
        if political_result and political_result.get('found'):
            # Enhance with actual numbers if available
            if political_result.get('verdict') in ['false', 'mostly_false']:
                political_result = self._add_actual_numbers(claim, political_result)
            return self._enhance_result(claim, political_result, temporal_info)
        
        # 6. Google Fact Check with better handling
        if self.google_api_key:
            google_result = self._check_google_enhanced(claim_adjusted)
            if google_result['found']:
                return self._enhance_result(claim, google_result, temporal_info)
        
        # 7. Pattern analysis
        pattern_result = self._analyze_claim_patterns(claim)
        if pattern_result['found']:
            return self._enhance_result(claim, pattern_result, temporal_info)
        
        # Default intelligent analysis
        return self._create_intelligent_result(claim, temporal_info)
    
    def _extract_temporal_context(self, claim: str) -> Dict:
        """Extract temporal context from claim"""
        context = {}
        
        # Check for partial year references
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
        
        # Extract specific time periods
        if 'first' in claim.lower():
            if re.search(r'first (\d+) months?', claim, re.IGNORECASE):
                context['time_period'] = 'specific_months'
            elif re.search(r'first (?:quarter|half|week|day)', claim, re.IGNORECASE):
                context['time_period'] = 'specific_period'
        
        return context
    
    def _adjust_partial_year_claim(self, claim: str) -> str:
        """Adjust claims about partial year data"""
        # Don't change the claim text, but add context in the result
        return claim
    
    def _verify_statement_source(self, claim: str, person: str) -> Optional[Dict]:
        """Verify if a person actually made a statement"""
        # Check cache first
        cache_key = f"{person.lower()}_{claim[:50]}"
        if cache_key in self.recent_statements:
            cached = self.recent_statements[cache_key]
            if datetime.now() - cached['time'] < self.statement_cache_duration:
                return cached['result']
        
        # For Netanyahu and other major figures, be more nuanced
        explanation = (
            f"This claim attributes a statement to {person}. While multiple news sources "
            f"may have reported similar claims, verification requires checking primary sources "
            f"such as official transcripts, video recordings, or official government statements. "
            f"Without access to these primary sources, we cannot definitively verify the exact wording."
        )
        
        result = {
            'claim': claim,
            'verdict': 'lacks_context',
            'confidence': 70,
            'explanation': explanation,
            'source': 'Statement Verification',
            'missing_context': 'Primary source verification needed (official transcript, video, or government release)',
            'api_response': False
        }
        
        # Cache the result
        self.recent_statements[cache_key] = {
            'time': datetime.now(),
            'result': result
        }
        
        return result
    
    def _check_ukraine_war_claim(self, claim: str) -> Optional[Dict]:
        """Handle Ukraine war claims with proper historical context"""
        claim_lower = claim.lower()
        
        # Check what aspect is being discussed
        if any(phrase in claim_lower for phrase in ['war started', 'war began', 'started the war']):
            if 'biden' in claim_lower or '2022' in claim:
                return {
                    'claim': claim,
                    'verdict': 'mostly_true',
                    'confidence': 85,
                    'explanation': (
                        "This is largely accurate. While Russia-Ukraine conflict has roots dating to 2014 "
                        "with the annexation of Crimea, the current full-scale war began on February 24, 2022, "
                        "during the Biden presidency. The speaker appears to be referring to this current phase "
                        "of the conflict, which is the deadliest and most extensive."
                    ),
                    'source': 'Historical Timeline',
                    'context_note': 'Distinguishing between 2014 regional conflict and 2022 full invasion',
                    'api_response': False
                }
            elif '2014' in claim:
                return {
                    'claim': claim,
                    'verdict': 'lacks_context',
                    'confidence': 80,
                    'explanation': (
                        "This requires context. Russia did annex Crimea and support separatists in Eastern "
                        "Ukraine starting in 2014. However, the current full-scale invasion began in 2022. "
                        "The claim is accurate about 2014 but may conflate two distinct phases of conflict."
                    ),
                    'source': 'Historical Timeline',
                    'missing_context': 'The 2014 conflict was regional; 2022 marked full-scale invasion',
                    'api_response': False
                }
        
        return None
    
    def _check_border_percentage_claim(self, claim: str) -> Optional[Dict]:
        """Handle border crossing percentage claims correctly"""
        if '90%' in claim and 'down' in claim.lower() and 'border' in claim.lower():
            # Extract the actual context
            numbers = re.findall(r'(\d+(?:,\d+)?)', claim)
            
            explanation = (
                "This claim states that border crossings are down 90%, meaning they have decreased "
                "by 90% from a previous level. This is a percentage decrease, not an absolute number. "
                "For example, if there were 1,000 crossings before, a 90% decrease would mean there "
                "are now 100 crossings (not 90 crossings)."
            )
            
            # Try to get actual data
            current_year = datetime.now().year
            if self.political_checker:
                # Get recent border data
                recent_data = self.political_checker.immigration_data.get(f'border_encounters_{current_year}', 0)
                last_year_data = self.political_checker.immigration_data.get(f'border_encounters_{current_year-1}', 0)
                
                if recent_data and last_year_data:
                    actual_decrease = ((last_year_data - recent_data) / last_year_data) * 100
                    
                    if abs(actual_decrease - 90) < 10:  # Within reasonable range
                        verdict = 'mostly_true'
                        explanation += f" Current data shows approximately {actual_decrease:.1f}% decrease."
                    else:
                        verdict = 'false'
                        explanation += f" However, actual data shows only a {actual_decrease:.1f}% change, not 90%."
                else:
                    verdict = 'unverified'
            else:
                verdict = 'unverified'
            
            return {
                'claim': claim,
                'verdict': verdict,
                'confidence': 75,
                'explanation': explanation,
                'source': 'Border Statistics Analysis',
                'interpretation_note': 'Percentage decrease, not absolute number',
                'api_response': False
            }
        
        return None
    
    def _add_actual_numbers(self, claim: str, result: Dict) -> Dict:
        """Add actual numbers to false claims when available"""
        if 'explanation' in result:
            # Look for number patterns in the original explanation
            claimed_match = re.search(r'claimed?\s+(\d+(?:,\d+)?(?:\.\d+)?(?:\s*(?:million|billion))?)', 
                                    result['explanation'], re.IGNORECASE)
            actual_match = re.search(r'actual(?:ly)?\s+(\d+(?:,\d+)?(?:\.\d+)?(?:\s*(?:million|billion))?)', 
                                   result['explanation'], re.IGNORECASE)
            
            if claimed_match and actual_match:
                result['claimed_value'] = claimed_match.group(1)
                result['actual_value'] = actual_match.group(1)
                result['explanation'] = (
                    f"{result['explanation']} "
                    f"The actual number is {result['actual_value']}, not {result['claimed_value']} as stated."
                )
        
        return result
    
    def _check_google_enhanced(self, claim: str) -> Dict:
        """Enhanced Google fact check with better source handling"""
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
                
                if 'claims' in data:
                    # Prioritize recent and reputable sources
                    best_result = None
                    best_score = 0
                    
                    for claim_data in data['claims']:
                        review = claim_data.get('claimReview', [{}])[0]
                        rating = review.get('textualRating', '').lower()
                        publisher = review.get('publisher', {}).get('name', '')
                        
                        # Score based on rating and publisher
                        score = self._score_fact_check_source(rating, publisher)
                        
                        if score > best_score:
                            best_score = score
                            best_result = self._parse_google_result(claim_data)
                    
                    if best_result:
                        return best_result
            
        except Exception as e:
            logger.error(f"Google fact check error: {str(e)}")
        
        return {'found': False}
    
    def _score_fact_check_source(self, rating: str, publisher: str) -> int:
        """Score fact check sources by reliability"""
        score = 0
        
        # Rating scores
        rating_scores = {
            'true': 10,
            'mostly true': 8,
            'half true': 5,
            'mostly false': 3,
            'false': 10,  # High score because we want to catch false claims
            'pants on fire': 10
        }
        score += rating_scores.get(rating, 0)
        
        # Publisher scores
        reputable_publishers = [
            'factcheck.org', 'politifact', 'snopes', 'associated press',
            'reuters', 'washington post', 'new york times', 'bbc'
        ]
        
        publisher_lower = publisher.lower()
        for pub in reputable_publishers:
            if pub in publisher_lower:
                score += 5
                break
        
        return score
    
    def _parse_google_result(self, claim_data: Dict) -> Dict:
        """Parse Google fact check result with enhancements"""
        review = claim_data.get('claimReview', [{}])[0]
        
        rating = review.get('textualRating', 'Unverified').lower()
        verdict_map = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mixture': 'mixed',
            'mostly false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'half true': 'mixed',
            'barely true': 'mostly_false'
        }
        
        return {
            'found': True,
            'verdict': verdict_map.get(rating, 'unverified'),
            'confidence': 80,
            'explanation': review.get('title', 'Fact check result available'),
            'source': review.get('publisher', {}).get('name', 'Fact Checker'),
            'url': review.get('url', ''),
            'api_response': True
        }
    
    def _analyze_claim_patterns(self, claim: str) -> Dict:
        """Enhanced pattern analysis"""
        claim_lower = claim.lower()
        
        # Absolute statements
        absolute_patterns = [
            (r'\b(never|always|every|all|none|no one|everyone|nobody)\b', 
             'Absolute claims are rarely entirely accurate. Real-world scenarios typically have exceptions.'),
            (r'\b(only|just|merely|solely|exclusively)\b',
             'Exclusive claims often oversimplify complex situations.'),
        ]
        
        for pattern, explanation in absolute_patterns:
            if re.search(pattern, claim_lower):
                return {
                    'found': True,
                    'verdict': 'lacks_context',
                    'confidence': 70,
                    'explanation': explanation,
                    'source': 'Pattern Analysis',
                    'pattern_type': 'absolute_statement',
                    'api_response': False
                }
        
        # Superlatives without context
        if re.search(r'\b(best|worst|most|least|biggest|smallest|largest|greatest)\b', claim_lower):
            if not re.search(r'(according to|based on|measured by|in terms of)', claim_lower):
                return {
                    'found': True,
                    'verdict': 'lacks_context',
                    'confidence': 65,
                    'explanation': (
                        'This superlative claim lacks specific criteria or context. '
                        'What metric is being used? What is the comparison group? '
                        'When was this measured?'
                    ),
                    'source': 'Pattern Analysis',
                    'missing_context': 'Specific metrics and comparison criteria needed',
                    'api_response': False
                }
        
        return {'found': False}
    
    def _create_intelligent_result(self, claim: str, temporal_info: Dict = None) -> Dict:
        """Create an intelligent result when no specific check matches"""
        result = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 40,
            'explanation': 'Unable to verify this claim with available sources.',
            'source': 'Automated Analysis',
            'api_response': False
        }
        
        # Add temporal context if present
        if temporal_info and temporal_info.get('partial_year'):
            result['temporal_note'] = (
                f"This claim refers to partial data from {temporal_info['year']}. "
                f"Complete annual data may not yet be available."
            )
        
        # Check if it's an opinion
        opinion_indicators = [
            'i think', 'i believe', 'in my opinion', 'it seems',
            'probably', 'might be', 'could be', 'should be'
        ]
        
        if any(indicator in claim.lower() for indicator in opinion_indicators):
            result['verdict'] = 'opinion'
            result['explanation'] = 'This appears to be an opinion rather than a factual claim.'
            result['confidence'] = 80
        
        return result
    
    def _create_error_result(self, claim: str) -> Dict:
        """Create result for claims that errored during checking"""
        return {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': 'An error occurred while checking this claim.',
            'source': 'Error',
            'api_response': False
        }
    
    def _enhance_result(self, original_claim: str, result: Dict, temporal_info: Dict = None) -> Dict:
        """Enhance result with claim text and temporal context"""
        result['claim'] = original_claim
        
        # Add temporal context if present
        if temporal_info:
            if temporal_info.get('partial_year'):
                result['temporal_context'] = (
                    f"Referring to partial {temporal_info['year']} data"
                )
            result['temporal_info'] = temporal_info
        
        # Ensure all required fields
        if 'confidence' not in result:
            result['confidence'] = 50
        if 'api_response' not in result:
            result['api_response'] = False
        
        return result
