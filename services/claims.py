"""
Enhanced Claims Extraction Service - Only Extract Verifiable Facts
"""
import re
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Extract only factual, verifiable claims from transcripts"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self.openai_client = None
        
        if openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized for claims extraction")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # NON-CLAIMS - Things we should NEVER extract
        self.non_claim_patterns = [
            # Greetings and pleasantries
            r"(?i)^(hello|hi|hey|good\s+(morning|afternoon|evening)|thank\s+you|thanks|welcome|glad\s+to|happy\s+to|pleased\s+to|delighted\s+to|excited\s+to|honored\s+to)",
            r"(?i)(thank\s+you\s+for|thanks\s+for|appreciate|grateful)",
            r"(?i)(how\s+are\s+you|hope\s+you|wish\s+you)",
            
            # Personal feelings/opinions without facts
            r"(?i)^(i\s+think|i\s+believe|i\s+feel|i\s+hope|i\s+wish|in\s+my\s+opinion|personally)",
            r"(?i)^(it\s+seems|it\s+appears|apparently|supposedly)",
            
            # Vague statements
            r"(?i)^(some\s+people|many\s+people|everyone\s+knows|they\s+say|people\s+say)",
            r"(?i)^(obviously|clearly|surely|certainly)(?!\s+\d)",  # Unless followed by numbers
            
            # Questions
            r"\?$",
            
            # Single words or very short
            r"^(\w+\s*){1,3}$",  # Less than 4 words
            
            # Pure subjective adjectives
            r"(?i)^(it('s|s|\s+is)\s+)?(great|wonderful|terrible|horrible|amazing|fantastic|awful|beautiful|ugly)(?!\s+that)",
        ]
        
        # FACTUAL CLAIM PATTERNS - What we SHOULD extract
        self.factual_patterns = [
            # Numbers and statistics
            r"\b\d+\.?\d*\s*(%|percent|percentage)",
            r"\b\d{1,3}(,\d{3})*(\.\d+)?\s*(million|billion|trillion|thousand)",
            r"\$\s*\d{1,3}(,\d{3})*(\.\d+)?\s*(million|billion|trillion)?",
            
            # Comparisons with data
            r"(increased?|decreased?|rose|fell|dropped|gained|lost)\s+by\s+\d+",
            r"(up|down)\s+\d+\.?\d*\s*(%|percent|percentage)",
            r"(more|less|fewer)\s+than\s+\d+",
            
            # Time-based claims
            r"(since|during|between|from|in)\s+(19|20)\d{2}",
            r"(first|last|only)\s+time\s+(since|in)",
            r"(highest|lowest|biggest|smallest|largest)\s+(since|in|ever)",
            
            # Policy/legislative claims
            r"(passed|signed|vetoed|approved|rejected|enacted|repealed)\s+(?:a\s+)?(law|bill|legislation|act|policy)",
            r"(created|eliminated|added|removed|cut)\s+\d+\s*(jobs|positions|programs)",
            
            # Definitive factual statements
            r"(unemployment|inflation|gdp|deficit|debt|crime\s+rate|murder\s+rate)\s+(is|was|reached|hit)\s+\d+",
            r"(spent|allocated|budgeted|invested)\s+\$?\d+",
            
            # Historical events
            r"(happened|occurred|took\s+place)\s+(on|in)\s+(January|February|March|April|May|June|July|August|September|October|November|December)",
            r"(founded|established|created|built)\s+in\s+\d{4}",
        ]
        
        # Keywords that indicate verifiable facts
        self.fact_keywords = [
            # Economic terms
            'unemployment', 'inflation', 'gdp', 'deficit', 'debt', 'budget',
            'revenue', 'spending', 'taxes', 'tariffs', 'trade', 'exports', 'imports',
            
            # Crime/safety
            'crime rate', 'murder rate', 'homicides', 'violent crime', 'arrests',
            'convictions', 'prison', 'incarceration',
            
            # Healthcare
            'insurance', 'premiums', 'coverage', 'medicare', 'medicaid', 'obamacare',
            'prescription', 'hospitals', 'doctors',
            
            # Immigration
            'border crossings', 'deportations', 'immigrants', 'refugees', 'asylum',
            'visas', 'citizenship',
            
            # Climate/environment
            'temperature', 'emissions', 'carbon', 'renewable', 'fossil fuels',
            'pollution', 'clean energy',
            
            # Education
            'graduation rate', 'test scores', 'literacy', 'schools', 'teachers',
            'tuition', 'student debt',
        ]
    
    def extract(self, transcript: str) -> Dict:
        """Extract only verifiable factual claims"""
        try:
            # Try AI extraction first if available
            if self.openai_client:
                ai_result = self._extract_with_ai_strict(transcript)
                if ai_result and ai_result.get('claims'):
                    # Filter AI results through our patterns too
                    filtered_claims = self._filter_claims(ai_result['claims'])
                    ai_result['claims'] = filtered_claims
                    return ai_result
            
            # Fallback to pattern-based extraction
            return self._extract_with_patterns_strict(transcript)
            
        except Exception as e:
            logger.error(f"Error extracting claims: {e}")
            return {
                'claims': [],
                'speakers': [],
                'topics': [],
                'extraction_method': 'error'
            }
    
    def _extract_with_ai_strict(self, transcript: str) -> Optional[Dict]:
        """Use AI with strict instructions to extract only factual claims"""
        try:
            # Limit transcript length for API
            transcript_excerpt = transcript[:10000] if len(transcript) > 10000 else transcript
            
            prompt = f"""Extract ONLY verifiable factual claims from this transcript.

IMPORTANT: Only extract statements that:
1. Contain specific numbers, dates, or statistics
2. Make claims about laws, policies, or historical events
3. State something happened/exists that can be verified with data
4. Compare quantities or rates

DO NOT extract:
- Opinions or feelings ("I think", "I believe")
- Greetings or pleasantries ("Happy to be here")
- Vague statements ("Many people say")
- Predictions about the future
- Personal preferences
- Questions

For each claim, provide:
- The EXACT complete sentence containing the claim
- The speaker name
- A note on what specifically can be fact-checked

Format as JSON:
[{{"text": "exact claim sentence", "speaker": "name", "checkable": "what to verify"}}]

Transcript:
{transcript_excerpt}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4-1106-preview" if "gpt-4" in str(self.openai_api_key) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a fact-checking expert. Extract ONLY verifiable factual claims, not opinions or pleasantries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low temperature for consistency
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                if content.startswith('['):
                    claims_data = json.loads(content)
                else:
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        claims_data = json.loads(json_match.group())
                    else:
                        return None
            except json.JSONDecodeError:
                logger.error("Failed to parse AI response as JSON")
                return None
            
            # Extract speakers
            speakers = list(set(claim.get('speaker', '') for claim in claims_data if claim.get('speaker')))
            
            # Extract topics based on content
            topics = self._extract_topics(transcript)
            
            return {
                'claims': claims_data,
                'speakers': [s for s in speakers if s and s != 'Unknown'],
                'topics': topics,
                'extraction_method': 'ai_strict'
            }
            
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return None
    
    def _extract_with_patterns_strict(self, transcript: str) -> Dict:
        """Extract claims using strict pattern matching"""
        claims = []
        speakers = []
        
        # Split into sentences
        sentences = self._split_into_sentences(transcript)
        
        # Track current speaker
        current_speaker = "Unknown"
        speaker_pattern = r'^([A-Z][A-Z\s\.]+):|^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]'
        
        for sentence in sentences:
            # Check for speaker change
            speaker_match = re.match(speaker_pattern, sentence)
            if speaker_match:
                current_speaker = speaker_match.group(1) or speaker_match.group(2)
                if current_speaker not in speakers:
                    speakers.append(current_speaker)
                sentence = re.sub(speaker_pattern, '', sentence).strip()
            
            # Skip if too short
            if len(sentence.split()) < 5:
                continue
            
            # Skip if matches non-claim patterns
            is_non_claim = False
            for pattern in self.non_claim_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    is_non_claim = True
                    break
            
            if is_non_claim:
                continue
            
            # Check if contains factual patterns
            is_factual = False
            
            # Must contain at least one factual pattern
            for pattern in self.factual_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    is_factual = True
                    break
            
            # OR contains fact keywords with numbers
            if not is_factual:
                sentence_lower = sentence.lower()
                has_keyword = any(keyword in sentence_lower for keyword in self.fact_keywords)
                has_number = bool(re.search(r'\b\d+\.?\d*\b', sentence))
                
                if has_keyword and has_number:
                    is_factual = True
            
            # Add if factual
            if is_factual:
                claims.append({
                    'text': sentence.strip(),
                    'speaker': current_speaker,
                    'checkable': 'Numerical or policy claim'
                })
        
        # Extract topics
        topics = self._extract_topics(transcript)
        
        return {
            'claims': claims[:50],  # Limit to 50 claims
            'speakers': speakers,
            'topics': topics,
            'extraction_method': 'pattern_strict'
        }
    
    def _filter_claims(self, claims: List[Dict]) -> List[Dict]:
        """Filter claims to remove non-factual statements"""
        filtered = []
        
        for claim in claims:
            text = claim.get('text', '')
            
            # Skip if too short
            if len(text.split()) < 5:
                continue
            
            # Skip if matches non-claim pattern
            is_non_claim = False
            for pattern in self.non_claim_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    is_non_claim = True
                    break
            
            if is_non_claim:
                continue
            
            # Must have some factual indicator
            has_number = bool(re.search(r'\b\d+\.?\d*\b', text))
            has_date = bool(re.search(r'\b(19|20)\d{2}\b', text))
            has_keyword = any(keyword in text.lower() for keyword in self.fact_keywords)
            has_pattern = any(re.search(pattern, text, re.IGNORECASE) for pattern in self.factual_patterns)
            
            if has_pattern or (has_keyword and (has_number or has_date)):
                filtered.append(claim)
        
        return filtered
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Remove timestamps
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
        text = re.sub(r'\[\d{2}:\d{2}\]', '', text)
        
        # Split on sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Clean up
        cleaned = []
        for sent in sentences:
            sent = sent.strip()
            if sent and len(sent) > 10:  # Minimum length
                cleaned.append(sent)
        
        return cleaned
    
    def _extract_topics(self, transcript: str) -> List[str]:
        """Extract main topics from transcript"""
        topics = []
        transcript_lower = transcript.lower()
        
        topic_keywords = {
            'economy': ['economy', 'jobs', 'unemployment', 'inflation', 'taxes'],
            'healthcare': ['healthcare', 'insurance', 'medicare', 'medicaid'],
            'immigration': ['immigration', 'border', 'immigrants', 'asylum'],
            'crime': ['crime', 'safety', 'police', 'violence'],
            'education': ['education', 'schools', 'students', 'teachers'],
            'climate': ['climate', 'environment', 'energy', 'emissions'],
            'foreign policy': ['china', 'russia', 'ukraine', 'israel', 'nato'],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    # Keep compatibility method
    def extract_claims_enhanced(self, transcript: str, use_ai: bool = True) -> List[Dict]:
        """Enhanced claim extraction (for compatibility)"""
        result = self.extract(transcript)
        return result.get('claims', [])
