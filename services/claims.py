"""
Balanced Claims Extraction Service
Extracts factual claims while being practical about what constitutes a verifiable statement
"""
import re
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Extract factual claims from transcripts with a balanced approach"""
    
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
    
    def extract(self, transcript: str) -> Dict:
        """Extract factual claims from transcript"""
        try:
            # Clean transcript
            transcript = transcript.strip()
            if not transcript:
                return {
                    'claims': [],
                    'speakers': [],
                    'topics': [],
                    'extraction_method': 'empty'
                }
            
            # Try AI extraction first if available
            if self.openai_client:
                try:
                    ai_result = self._extract_with_ai(transcript)
                    if ai_result and ai_result.get('claims'):
                        return ai_result
                except Exception as e:
                    logger.error(f"AI extraction failed: {e}")
            
            # Fallback to pattern-based extraction
            return self._extract_with_patterns(transcript)
            
        except Exception as e:
            logger.error(f"Error extracting claims: {e}")
            return {
                'claims': [],
                'speakers': [],
                'topics': [],
                'extraction_method': 'error'
            }
    
    def _extract_with_ai(self, transcript: str) -> Optional[Dict]:
        """Use AI to extract claims"""
        try:
            # Limit transcript length for API
            max_length = 8000
            if len(transcript) > max_length:
                transcript = transcript[:max_length] + "..."
            
            prompt = f"""Extract factual claims from this transcript that can be fact-checked.

Include statements that:
- Make specific claims about events, people, or things
- State facts that can be verified
- Include numbers, dates, or statistics
- Make comparisons or assertions
- Claim something happened or exists

Exclude:
- Pure opinions like "I think" or "I believe"
- Greetings and pleasantries
- Questions
- Future predictions or hypotheticals

For each claim, provide:
- The complete statement
- Who said it (if clear)
- Why it's checkable

Format as JSON array: [{{"text": "claim", "speaker": "name", "context": "brief context"}}]

Transcript:
{transcript}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract factual claims for fact-checking. Be thorough but selective."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                if content.startswith('['):
                    claims_data = json.loads(content)
                else:
                    # Try to find JSON in response
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        claims_data = json.loads(json_match.group())
                    else:
                        logger.error("No JSON found in AI response")
                        return None
                        
                # Process claims
                processed_claims = []
                speakers = set()
                
                for claim in claims_data:
                    if isinstance(claim, dict) and claim.get('text'):
                        text = claim['text'].strip()
                        speaker = claim.get('speaker', 'Unknown').strip()
                        
                        # Basic validation
                        if len(text.split()) >= 5 and not text.endswith('?'):
                            processed_claims.append({
                                'text': text,
                                'speaker': speaker,
                                'context': claim.get('context', '')
                            })
                            if speaker and speaker != 'Unknown':
                                speakers.add(speaker)
                
                return {
                    'claims': processed_claims[:30],  # Limit to 30 claims
                    'speakers': list(speakers),
                    'topics': self._extract_topics(transcript),
                    'extraction_method': 'ai'
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                return None
            
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return None
    
    def _extract_with_patterns(self, transcript: str) -> Dict:
        """Extract claims using pattern matching"""
        claims = []
        speakers = set()
        
        # Split into sentences
        sentences = self._split_into_sentences(transcript)
        
        # Track current speaker
        current_speaker = "Unknown"
        
        for sentence in sentences:
            # Check for speaker pattern (NAME: or [NAME])
            speaker_match = re.match(r'^([A-Z][A-Za-z\s\.]+):|^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]', sentence)
            if speaker_match:
                current_speaker = speaker_match.group(1) or speaker_match.group(2)
                speakers.add(current_speaker)
                # Remove speaker prefix
                sentence = re.sub(r'^[^:]+:\s*', '', sentence)
                sentence = re.sub(r'^\[[^\]]+\]\s*', '', sentence)
            
            # Clean sentence
            sentence = sentence.strip()
            
            # Skip if too short or is a question
            if len(sentence.split()) < 5 or sentence.endswith('?'):
                continue
            
            # Check if it's a factual claim
            if self._is_factual_claim(sentence):
                claims.append({
                    'text': sentence,
                    'speaker': current_speaker,
                    'context': ''
                })
        
        return {
            'claims': claims[:30],  # Limit to 30 claims
            'speakers': list(speakers),
            'topics': self._extract_topics(transcript),
            'extraction_method': 'pattern'
        }
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """Check if a sentence is a factual claim worth checking"""
        sentence_lower = sentence.lower()
        
        # Skip pure opinions and feelings
        opinion_starters = [
            'i think', 'i believe', 'i feel', 'in my opinion',
            'it seems', 'it appears', 'i hope', 'i wish'
        ]
        if any(sentence_lower.startswith(starter) for starter in opinion_starters):
            return False
        
        # Skip greetings and pleasantries
        greeting_patterns = [
            r'^(hello|hi|hey|good\s+(morning|afternoon|evening))',
            r'^(thank\s+you|thanks|welcome|glad\s+to)',
            r'^(nice\s+to|pleased\s+to|happy\s+to)'
        ]
        for pattern in greeting_patterns:
            if re.match(pattern, sentence_lower):
                return False
        
        # Look for factual indicators
        factual_indicators = [
            # Has numbers
            r'\b\d+',
            # Has percentages
            r'\d+\s*%|\d+\s+percent',
            # Has money
            r'\$\d+|\d+\s+dollars?',
            # Has dates/years
            r'\b(19|20)\d{2}\b',
            # Has comparisons
            r'\b(more|less|fewer|greater|higher|lower|bigger|smaller)\s+than\b',
            # Has specific verbs indicating facts
            r'\b(is|are|was|were|has|have|had|increased|decreased|rose|fell|gained|lost)\b',
            # Has definitive statements
            r'\b(always|never|every|all|none|only|first|last)\b',
            # Policy/law references
            r'\b(law|bill|act|policy|regulation|amendment)\b',
            # Achievement claims
            r'\b(won|lost|achieved|created|built|destroyed|passed|failed)\b'
        ]
        
        # Check if it has at least one factual indicator
        for pattern in factual_indicators:
            if re.search(pattern, sentence_lower):
                return True
        
        # Check for named entities (people, places, organizations)
        # Simple heuristic: has multiple capitalized words
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', sentence)
        if len(capitalized_words) >= 2:
            return True
        
        # Check if it makes a claim about something
        claim_patterns = [
            r'.*\s+(is|are|was|were)\s+.*',  # X is Y
            r'.*\s+(has|have|had)\s+.*',      # X has Y
            r'.*\s+(will|would|can|could)\s+.*',  # X will Y
            r'.*\s+(did|does|do)\s+.*',       # X did Y
        ]
        
        for pattern in claim_patterns:
            if re.match(pattern, sentence_lower):
                # Make sure it's not too vague
                vague_terms = ['it', 'this', 'that', 'they', 'them', 'something', 'someone']
                words = sentence_lower.split()
                if len(words) > 5 and not all(word in vague_terms for word in words[:3]):
                    return True
        
        return False
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Remove timestamps
        text = re.sub(r'\[\d{1,2}:\d{2}:\d{2}\]', '', text)
        text = re.sub(r'\[\d{1,2}:\d{2}\]', '', text)
        text = re.sub(r'\(\d{1,2}:\d{2}:\d{2}\)', '', text)
        
        # Replace line breaks with spaces
        text = re.sub(r'\n+', ' ', text)
        
        # Split on sentence endings
        # But be careful with abbreviations
        text = re.sub(r'\b(Mr|Mrs|Dr|Ms|Prof|Sr|Jr)\.\s*', r'\1<PERIOD> ', text)
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Restore periods in abbreviations
        sentences = [s.replace('<PERIOD>', '.') for s in sentences]
        
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
            'economy': ['economy', 'jobs', 'unemployment', 'inflation', 'taxes', 'budget'],
            'healthcare': ['healthcare', 'insurance', 'medicare', 'medicaid', 'obamacare'],
            'immigration': ['immigration', 'border', 'immigrants', 'citizenship'],
            'education': ['education', 'schools', 'students', 'teachers', 'college'],
            'climate': ['climate', 'environment', 'energy', 'pollution'],
            'crime': ['crime', 'police', 'safety', 'violence'],
            'foreign policy': ['china', 'russia', 'war', 'military', 'nato'],
            'covid-19': ['covid', 'coronavirus', 'pandemic', 'vaccine'],
            'elections': ['election', 'voting', 'campaign', 'ballot']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:5]  # Limit to top 5 topics
    
    # Compatibility method
    def extract_claims_enhanced(self, transcript: str, use_ai: bool = True) -> List[Dict]:
        """Legacy method for compatibility"""
        result = self.extract(transcript)
        return result.get('claims', [])
