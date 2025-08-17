"""
Enhanced Claims Extraction Module with AI Filtering
Intelligently extracts factual claims while filtering conversational content
"""
import re
import logging
import requests
from typing import List, Dict, Optional, Tuple
import spacy
from collections import defaultdict

logger = logging.getLogger(__name__)

class ClaimsExtractor:
    """Advanced claims extraction with AI-powered filtering"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            logger.warning("spaCy model not loaded. Some features may be limited.")
            self.nlp = None
        
        # Enhanced conversational patterns
        self.conversational_patterns = [
            # Greetings and pleasantries
            r"^(good\s+)?(morning|afternoon|evening|day)",
            r"^(hi|hello|hey|greetings|welcome)",
            r"^(thank\s*you|thanks|appreciate|grateful)",
            r"^(it'?s\s+)?(great|good|nice|wonderful|pleasure|honor)\s+to\s+(see|be|have|meet)",
            r"^(how\s+are|how'?s\s+everyone|hope\s+you)",
            
            # Transition phrases
            r"^(so|well|now|anyway|alright|okay)",
            r"^(let'?s|let\s+me|allow\s+me|can\s+i|may\s+i)",
            r"^(moving\s+on|turning\s+to|next)",
            
            # Meta-discourse
            r"^(as\s+i\s+said|like\s+i\s+mentioned|i\s+mean)",
            r"^(you\s+know|i\s+think|in\s+my\s+opinion)",
            
            # Filler
            r"^(um+|uh+|er+|ah+|oh+|hmm+)",
            r"^(basically|essentially|actually|literally)",
            
            # Acknowledgments
            r"^(yes|yeah|yep|no|nope|okay|alright|sure|right)",
            r"^(i\s+see|i\s+understand|got\s+it|makes\s+sense)",
        ]
        
        # Factual indicators (enhanced)
        self.factual_indicators = {
            'statistical': [
                r'\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:percent|%)',
                r'\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:million|billion|trillion)',
                r'\b\d+(?:,\d+)*\s+(?:people|dollars|cases|deaths|votes)',
                r'(?:increased?|decreased?|rose|fell|grew)\s+(?:by\s+)?\d+',
                r'(?:up|down)\s+\d+(?:\.\d+)?\s*(?:percent|%)',
            ],
            'temporal': [
                r'(?:in|since|during|before|after)\s+(?:19|20)\d{2}',
                r'(?:last|next|this)\s+(?:year|month|week|decade)',
                r'(?:yesterday|today|tomorrow|recently)',
                r'(?:currently|now|at\s+present|as\s+of)',
                r'thus far in \d{4}',
                r'so far (?:this|in) \d{4}',
            ],
            'comparative': [
                r'(?:more|less|fewer)\s+than',
                r'(?:compared\s+to|versus|vs\.?)',
                r'(?:highest|lowest|biggest|smallest)\s+(?:in|since|ever)',
                r'(?:better|worse)\s+than',
            ],
            'definitive': [
                r'(?:^|\s)(?:is|are|was|were)\s+(?:the\s+)?(?:first|last|only)',
                r'(?:never|always|every|all|none)\s+',
                r'(?:definitely|certainly|absolutely|surely)',
                r'(?:proved?n?|confirmed?|verified?)',
            ],
            'attribution': [
                r'according\s+to\s+(?:[A-Z][a-z]+|the)',
                r'(?:[A-Z][a-z]+\s+)?(?:said|stated|claimed|announced)',
                r'(?:study|report|poll|survey)\s+(?:shows?|found|revealed)',
                r'(?:data|statistics|numbers)\s+(?:show|indicate|suggest)',
            ]
        }
        
        # Topics that often contain factual claims
        self.factual_topics = [
            'economy', 'inflation', 'unemployment', 'gdp', 'deficit',
            'immigration', 'border', 'crime', 'murder', 'violence',
            'healthcare', 'insurance', 'medicare', 'medicaid',
            'climate', 'temperature', 'emissions', 'renewable',
            'election', 'votes', 'ballots', 'fraud', 'results',
            'war', 'military', 'troops', 'casualties', 'spending',
            'education', 'schools', 'students', 'teachers', 'literacy',
            'covid', 'vaccine', 'deaths', 'cases', 'pandemic',
            'arrest', 'criminal', 'alien', 'illegal'
        ]
    
    def extract_claims(self, transcript: str, max_claims: int = 50) -> List[Dict]:
        """Extract factual claims with AI-enhanced filtering"""
        if not transcript:
            return []
        
        # Step 1: Split into sentences
        sentences = self._split_into_sentences(transcript)
        
        # Step 2: Initial filtering - remove obvious non-claims
        potential_claims = []
        for sent in sentences:
            if not self._is_conversational(sent) and len(sent.split()) > 4:
                potential_claims.append(sent)
        
        # Step 3: Score each potential claim
        scored_claims = []
        for claim in potential_claims:
            score = self._score_claim(claim)
            if score > 0:
                scored_claims.append({
                    'text': claim,
                    'score': score,
                    'indicators': self._get_claim_indicators(claim),
                    'word_count': len(claim.split())
                })
        
        # Step 4: AI filtering for ambiguous cases (if available)
        if self.openai_api_key and len(scored_claims) > 10:
            scored_claims = self._ai_filter_claims(scored_claims)
        
        # Step 5: Sort by score and take top claims
        scored_claims.sort(key=lambda x: x['score'], reverse=True)
        top_claims = scored_claims[:max_claims]
        
        # Step 6: Final cleanup
        final_claims = []
        for claim_data in top_claims:
            cleaned = self._clean_claim(claim_data['text'])
            if cleaned:
                claim_data['text'] = cleaned
                final_claims.append(claim_data)
        
        logger.info(f"Extracted {len(final_claims)} factual claims from {len(sentences)} sentences")
        return final_claims
    
    def extract_context(self, transcript: str) -> Tuple[List[str], List[str]]:
        """Extract speakers and topics from transcript"""
        speakers = []
        topics = []
        
        # Clean transcript
        lines = transcript.split('\n')
        
        # Look for speaker patterns
        speaker_patterns = [
            r'^([A-Z][A-Z\s\.]+):',  # ALL CAPS speaker
            r'^((?:President|Mr\.|Ms\.|Dr\.|Senator|Representative|Governor) [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?):',
            r'^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]',  # [Speaker Name]
        ]
        
        for line in lines[:50]:  # Check first 50 lines
            for pattern in speaker_patterns:
                match = re.match(pattern, line)
                if match:
                    speaker = match.group(1).strip()
                    if speaker not in speakers and len(speaker) < 50:
                        speakers.append(speaker)
        
        # Extract topics
        text_lower = transcript.lower()
        topic_keywords = {
            'immigration': ['immigration', 'border', 'immigrant', 'asylum', 'deportation'],
            'economy': ['economy', 'inflation', 'unemployment', 'jobs', 'gdp', 'recession'],
            'healthcare': ['healthcare', 'medicare', 'medicaid', 'insurance', 'hospital'],
            'crime': ['crime', 'murder', 'violence', 'police', 'criminal', 'safety'],
            'climate': ['climate', 'warming', 'carbon', 'emissions', 'renewable', 'fossil'],
            'education': ['education', 'school', 'teacher', 'student', 'literacy', 'college'],
            'war': ['war', 'military', 'troops', 'conflict', 'invasion', 'ukraine', 'russia'],
        }
        
        for topic, keywords in topic_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            if count >= 2:  # Topic mentioned multiple times
                topics.append(topic)
        
        logger.info(f"Found {len(speakers)} speakers and {len(topics)} topics")
        return speakers, topics
    
    def filter_verifiable(self, claims: List[Dict]) -> List[Dict]:
        """Filter claims to only include verifiable factual statements"""
        verifiable = []
        
        for claim in claims:
            # Skip opinions and predictions
            if self._is_opinion(claim['text']) or self._is_prediction(claim['text']):
                continue
            
            # Skip claims that are too vague
            if self._is_too_vague(claim['text']):
                continue
            
            # Must have strong factual indicators
            if claim['score'] >= 2:
                verifiable.append(claim)
        
        logger.info(f"Filtered to {len(verifiable)} verifiable claims")
        return verifiable
    
    def prioritize_claims(self, claims: List[Dict]) -> List[str]:
        """Prioritize claims by importance and verifiability"""
        # Calculate priority score for each claim
        for claim in claims:
            priority = claim['score']
            
            # Boost priority for statistical claims
            if 'statistical' in claim['indicators']:
                priority += 2
            
            # Boost priority for cited sources
            if 'attribution' in claim['indicators']:
                priority += 1
            
            # Boost priority for comparisons and superlatives
            if 'comparative' in claim['indicators']:
                priority += 1
            
            # Boost priority for temporal claims (2025, etc)
            if 'temporal' in claim['indicators']:
                priority += 1
            
            # Reduce priority for very long claims
            if claim['word_count'] > 50:
                priority -= 1
            
            claim['priority'] = priority
        
        # Sort by priority
        sorted_claims = sorted(claims, key=lambda x: x['priority'], reverse=True)
        
        # Return just the claim text strings for fact checking
        return [claim['text'] for claim in sorted_claims]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using multiple methods"""
        # Remove speaker labels
        text = re.sub(r'^[A-Z][A-Z\s\.]+:', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n[A-Z][A-Z\s\.]+:', '\n', text)
        text = re.sub(r'\[.*?\]', '', text)  # Remove bracketed content
        
        if self.nlp:
            # Use spaCy for sentence segmentation
            try:
                doc = self.nlp(text[:1000000])  # Limit to 1M chars for spaCy
                sentences = [sent.text.strip() for sent in doc.sents]
            except:
                # Fallback to regex if spaCy fails
                sentences = re.split(r'[.!?]+', text)
        else:
            # Fallback to regex
            sentences = re.split(r'[.!?]+', text)
        
        # Clean and filter
        cleaned = []
        for sent in sentences:
            sent = sent.strip()
            if sent and len(sent) > 20:  # Minimum length
                cleaned.append(sent)
        
        return cleaned
    
    def _is_conversational(self, text: str) -> bool:
        """Check if text is conversational/non-factual"""
        text_lower = text.lower().strip()
        
        # Check against patterns
        for pattern in self.conversational_patterns:
            if re.match(pattern, text_lower):
                return True
        
        # Check if it's a question (unless rhetorical)
        if text.strip().endswith('?') and not any(
            phrase in text_lower for phrase in ['did you know', 'isn\'t it true', 'remember when']
        ):
            return True
        
        # Check for pure opinion markers
        opinion_markers = [
            'in my opinion', 'i believe', 'i think', 'i feel',
            'it seems to me', 'personally', 'my view is'
        ]
        if any(marker in text_lower for marker in opinion_markers):
            return True
        
        return False
    
    def _score_claim(self, claim: str) -> int:
        """Score a claim based on factual indicators"""
        score = 0
        claim_lower = claim.lower()
        
        # Check each indicator type
        for category, patterns in self.factual_indicators.items():
            for pattern in patterns:
                if re.search(pattern, claim_lower):
                    if category == 'statistical':
                        score += 3
                    elif category == 'temporal':
                        score += 2
                    elif category == 'comparative':
                        score += 2
                    elif category == 'definitive':
                        score += 2
                    elif category == 'attribution':
                        score += 1
        
        # Check for factual topics
        for topic in self.factual_topics:
            if topic in claim_lower:
                score += 1
        
        # Penalize vague language
        vague_terms = ['some', 'many', 'few', 'several', 'various', 'certain']
        for term in vague_terms:
            if f' {term} ' in f' {claim_lower} ':
                score -= 1
        
        # Penalize short claims
        word_count = len(claim.split())
        if word_count < 8:
            score -= 2
        elif word_count > 15:
            score += 1
        
        return max(0, score)
    
    def _get_claim_indicators(self, claim: str) -> List[str]:
        """Get list of indicators present in claim"""
        indicators = []
        claim_lower = claim.lower()
        
        for category, patterns in self.factual_indicators.items():
            for pattern in patterns:
                if re.search(pattern, claim_lower):
                    indicators.append(category)
                    break
        
        return list(set(indicators))
    
    def _ai_filter_claims(self, claims: List[Dict]) -> List[Dict]:
        """Use AI to filter ambiguous claims"""
        if not self.openai_api_key:
            return claims
        
        try:
            # Batch process for efficiency
            batch_size = 10
            filtered_claims = []
            
            for i in range(0, len(claims), batch_size):
                batch = claims[i:i+batch_size]
                claim_texts = [c['text'] for c in batch]
                
                # Create prompt
                prompt = self._create_ai_filter_prompt(claim_texts)
                
                # Call OpenAI
                headers = {
                    'Authorization': f'Bearer {self.openai_api_key}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': 'gpt-3.5-turbo',
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are a fact-checking assistant that identifies verifiable factual claims.'
                        },
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0,
                    'max_tokens': 200
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
                    
                    # Parse response
                    keep_indices = self._parse_ai_filter_response(content)
                    
                    # Add claims that passed filter
                    for idx in keep_indices:
                        if idx < len(batch):
                            filtered_claims.append(batch[idx])
                else:
                    # On error, keep all claims
                    filtered_claims.extend(batch)
            
            return filtered_claims
            
        except Exception as e:
            logger.error(f"AI filtering failed: {str(e)}")
            return claims
    
    def _create_ai_filter_prompt(self, claims: List[str]) -> str:
        """Create prompt for AI filtering"""
        prompt = """Which of these statements are factual claims that can be fact-checked? 
        
A factual claim:
- Makes a specific assertion about reality
- Can be verified as true or false
- Is not purely opinion or greeting

For each statement, respond with its number if it's a factual claim.

Statements:
"""
        for i, claim in enumerate(claims):
            prompt += f"{i+1}. {claim}\n"
        
        prompt += "\nNumbers of factual claims (comma-separated):"
        
        return prompt
    
    def _parse_ai_filter_response(self, response: str) -> List[int]:
        """Parse AI response to get claim indices"""
        try:
            # Extract numbers from response
            numbers = re.findall(r'\d+', response)
            # Convert to 0-based indices
            return [int(n) - 1 for n in numbers if 0 < int(n) <= 10]
        except:
            return list(range(10))  # Keep all on error
    
    def _clean_claim(self, claim: str) -> str:
        """Clean and normalize claim text"""
        # Remove extra whitespace
        claim = ' '.join(claim.split())
        
        # Remove trailing punctuation if incomplete
        claim = claim.rstrip()
        
        # Ensure sentence ending
        if claim and claim[-1] not in '.!?':
            claim += '.'
        
        # Remove quotes if they're unmatched
        quote_count = claim.count('"')
        if quote_count % 2 != 0:
            claim = claim.replace('"', '')
        
        return claim
    
    def _is_opinion(self, text: str) -> bool:
        """Check if text is purely opinion"""
        opinion_phrases = [
            'i think', 'i believe', 'in my opinion', 'it seems',
            'i feel', 'personally', 'my view', 'i suppose'
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in opinion_phrases)
    
    def _is_prediction(self, text: str) -> bool:
        """Check if text is a prediction"""
        prediction_phrases = [
            'will be', 'going to', 'predict', 'forecast',
            'expect', 'anticipate', 'likely', 'probably'
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in prediction_phrases)
    
    def _is_too_vague(self, text: str) -> bool:
        """Check if text is too vague to verify"""
        # Very short
        if len(text.split()) < 6:
            return True
        
        # No specific claims
        vague_phrases = [
            'some people', 'many people', 'they say', 'everyone knows',
            'it is said', 'sources say', 'reports indicate'
        ]
        
        text_lower = text.lower()
        has_vague = any(phrase in text_lower for phrase in vague_phrases)
        has_specific = any(char.isdigit() for char in text) or any(
            word in text_lower for word in ['percent', 'million', 'billion', 'first', 'last', 'only']
        )
        
        return has_vague and not has_specific
