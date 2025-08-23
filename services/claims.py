"""
Balanced Claims Extraction Service
Extracts factual claims while being practical about what constitutes a verifiable statement
"""
import re
import logging
from typing import List, Dict, Optional, Set
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
        
        # Initialize comprehensive non-claim patterns
        self._initialize_non_claim_patterns()
    
    def _initialize_non_claim_patterns(self):
        """Initialize comprehensive patterns for non-claims"""
        # Phrases that are definitely not claims
        self.non_claim_phrases = {
            # Greetings
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'good night', 'greetings', 'welcome', 'howdy',
            
            # Farewells
            'goodbye', 'bye', 'farewell', 'see you', 'see you later', 'take care',
            'have a good day', 'have a great day', 'have a nice day',
            'have a good night', 'have a great night', 'catch you later',
            
            # Thanks and acknowledgments
            'thank you', 'thanks', 'thank you very much', 'thanks very much',
            'thank you so much', 'thanks so much', 'thanks a lot', 'many thanks',
            'much appreciated', 'appreciate it', 'appreciate that',
            'grateful', 'gratitude', 'thankful',
            
            # Responses to thanks
            'you\'re welcome', 'youre welcome', 'no problem', 'my pleasure',
            'anytime', 'sure thing', 'of course', 'no worries', 'don\'t mention it',
            
            # Pleasantries
            'please', 'excuse me', 'sorry', 'apologies', 'pardon me',
            'beg your pardon', 'forgive me', 'my apologies',
            
            # Agreement/acknowledgment
            'okay', 'ok', 'alright', 'sure', 'yes', 'no', 'yeah', 'nope',
            'uh huh', 'mm hmm', 'got it', 'understood', 'i see', 'right',
            'exactly', 'absolutely', 'definitely', 'certainly',
            
            # Conversational fillers
            'well', 'so', 'now', 'then', 'anyway', 'anyhow', 'however',
            'you know', 'i mean', 'basically', 'actually', 'literally',
            'like', 'um', 'uh', 'er', 'ah',
            
            # Questions that aren't claims
            'how are you', 'how do you do', 'what\'s up', 'how\'s it going',
            'how have you been', 'what\'s new',
            
            # Meta-conversational
            'let me', 'allow me', 'if i may', 'may i', 'can i',
            'let\'s', 'shall we', 'why don\'t we',
            
            # Ceremonial/formal
            'ladies and gentlemen', 'distinguished guests', 'dear friends',
            'it\'s an honor', 'it\'s a pleasure', 'privileged to',
            'delighted to', 'happy to', 'glad to'
        }
        
        # Regex patterns for non-claims
        self.non_claim_patterns = [
            # Greetings with optional names
            r'^(hello|hi|hey|greetings)(\s+\w+)?[.,!?]?$',
            r'^good\s+(morning|afternoon|evening|night)(\s+\w+)?[.,!?]?$',
            
            # Thank you variations
            r'^(thank\s+you|thanks)(\s+(very\s+)?much)?(\s+\w+)?[.,!?]?$',
            r'^(many\s+)?thanks(\s+to\s+\w+)?[.,!?]?$',
            r'^(much\s+)?appreciated?[.,!?]?$',
            
            # Short responses
            r'^(yes|no|yeah|nope|okay|ok|sure|alright)([.,!?]|$)',
            r'^(absolutely|definitely|certainly|exactly)([.,!?]|$)',
            
            # Apologetic phrases
            r'^(sorry|apologies|excuse\s+me|pardon\s+me)(\s+\w+)?[.,!?]?$',
            
            # Welcome responses
            r'^(you\'?re\s+)?(welcome|no\s+problem|my\s+pleasure)([.,!?]|$)',
            
            # Single word or very short
            r'^\w+[.,!?]?$',  # Single word
            r'^\w+\s+\w+[.,!?]?$',  # Two words
        ]
    
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
                        # Double-check AI results with our filters
                        filtered_claims = []
                        for claim in ai_result['claims']:
                            if self._is_valid_claim(claim['text']):
                                filtered_claims.append(claim)
                        
                        ai_result['claims'] = filtered_claims
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
- Greetings like "Hello", "Good morning"
- Thank you statements like "Thank you", "Thanks very much"
- Pleasantries and acknowledgments
- Questions
- Future predictions or hypotheticals
- Single words or very short phrases
- Conversational fillers like "You know", "I mean"
- Apologies or courtesy phrases

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
                    {"role": "system", "content": "Extract only factual claims for fact-checking. Exclude all pleasantries, greetings, and conversational elements."},
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
                        
                        # Validate claim
                        if self._is_valid_claim(text):
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
            
            # Check if it's a valid claim
            if self._is_valid_claim(sentence) and self._is_factual_claim(sentence):
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
    
    def _is_valid_claim(self, sentence: str) -> bool:
        """Check if sentence is valid for fact-checking (not a non-claim)"""
        if not sentence:
            return False
        
        sentence_clean = sentence.strip().lower()
        
        # Check length
        if len(sentence.split()) < 5:
            # For short sentences, be very strict
            # Check if it's just a pleasantry
            if sentence_clean in self.non_claim_phrases:
                return False
            
            # Check against patterns
            for pattern in self.non_claim_patterns:
                if re.match(pattern, sentence_clean):
                    return False
        
        # Skip questions
        if sentence.strip().endswith('?'):
            return False
        
        # Check if entire sentence is a non-claim phrase
        if sentence_clean in self.non_claim_phrases:
            return False
        
        # Check for non-claim patterns
        for pattern in self.non_claim_patterns:
            if re.match(pattern, sentence_clean):
                return False
        
        # Check if it starts with non-claim phrases
        for phrase in self.non_claim_phrases:
            if sentence_clean.startswith(phrase + ' ') or sentence_clean == phrase:
                # But allow if it contains factual content after
                remainder = sentence_clean[len(phrase):].strip()
                if len(remainder) < 10 or not any(char.isdigit() or char == '$' for char in remainder):
                    return False
        
        # Skip pure conversational elements
        conversational_only = [
            r'^(well|so|now|then|anyway|however)\s*[,.]?$',
            r'^(you know|i mean|basically|actually|literally)\s*[,.]?$',
            r'^(um|uh|er|ah|oh)\s*[,.]?$',
        ]
        
        for pattern in conversational_only:
            if re.match(pattern, sentence_clean):
                return False
        
        return True
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """Check if a sentence is a factual claim worth checking"""
        sentence_lower = sentence.lower()
        
        # Skip pure opinions and feelings
        opinion_starters = [
            'i think', 'i believe', 'i feel', 'in my opinion',
            'it seems', 'it appears', 'i hope', 'i wish',
            'i suppose', 'i guess', 'i assume'
        ]
        if any(sentence_lower.startswith(starter) for starter in opinion_starters):
            # But check if it's followed by a factual claim
            if not any(indicator in sentence_lower for indicator in [
                'that', 'because', 'since', 'due to', 'according to'
            ]):
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
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
            # Has comparisons
            r'\b(more|less|fewer|greater|higher|lower|bigger|smaller)\s+than\b',
            # Has specific verbs indicating facts
            r'\b(is|are|was|were|has|have|had|increased|decreased|rose|fell|gained|lost)\b',
            # Has definitive statements
            r'\b(always|never|every|all|none|only|first|last)\b',
            # Policy/law references
            r'\b(law|bill|act|policy|regulation|amendment)\b',
            # Achievement claims
            r'\b(won|lost|achieved|created|built|destroyed|passed|failed|elected|defeated)\b',
            # Statistical terms
            r'\b(average|median|mean|total|sum|count|number)\b',
            # Location references
            r'\b(country|state|city|nation|world|global|international)\b'
        ]
        
        # Check if it has at least one factual indicator
        has_factual_indicator = False
        for pattern in factual_indicators:
            if re.search(pattern, sentence_lower):
                has_factual_indicator = True
                break
        
        if not has_factual_indicator:
            # Check for named entities (people, places, organizations)
            # Simple heuristic: has multiple capitalized words
            capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', sentence)
            if len(capitalized_words) >= 2:
                has_factual_indicator = True
        
        if not has_factual_indicator:
            return False
        
        # Additional check: does it make a substantive claim?
        # Check if it has a subject-verb-object structure with meaningful content
        if has_factual_indicator:
            # Make sure it's not just a number or date in isolation
            words = sentence_lower.split()
            if len(words) < 4:
                # Too short to be a meaningful claim unless it's very specific
                if not re.search(r'\b(is|are|was|were)\b', sentence_lower):
                    return False
        
        return True
    
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
            'economy': ['economy', 'jobs', 'unemployment', 'inflation', 'taxes', 'budget', 'deficit', 'gdp'],
            'healthcare': ['healthcare', 'insurance', 'medicare', 'medicaid', 'obamacare', 'health care'],
            'immigration': ['immigration', 'border', 'immigrants', 'citizenship', 'deportation', 'asylum'],
            'education': ['education', 'schools', 'students', 'teachers', 'college', 'university', 'tuition'],
            'climate': ['climate', 'environment', 'energy', 'pollution', 'renewable', 'carbon', 'emissions'],
            'crime': ['crime', 'police', 'safety', 'violence', 'criminal', 'justice', 'prison'],
            'foreign policy': ['china', 'russia', 'war', 'military', 'nato', 'foreign', 'international'],
            'covid-19': ['covid', 'coronavirus', 'pandemic', 'vaccine', 'mask', 'lockdown'],
            'elections': ['election', 'voting', 'campaign', 'ballot', 'voter', 'candidate'],
            'infrastructure': ['infrastructure', 'roads', 'bridges', 'broadband', 'transportation'],
            'technology': ['technology', 'tech', 'internet', 'cyber', 'ai', 'artificial intelligence'],
            'trade': ['trade', 'tariff', 'import', 'export', 'nafta', 'treaty']
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
