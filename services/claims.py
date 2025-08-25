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
    """Extract factual claims from transcripts with improved filtering"""
    
    def __init__(self, config):
        self.config = config
        # Get max claims from config, default to 100 (was 30)
        self.max_claims = getattr(config, 'MAX_CLAIMS_PER_TRANSCRIPT', 100)
        
        openai_api_key = getattr(config, 'OPENAI_API_KEY', None)
        self.openai_client = None
        
        if openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized for claims extraction")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Initialize comprehensive non-claim patterns
        self._initialize_filters()
    
    def _initialize_filters(self):
        """Initialize comprehensive patterns for filtering out non-claims"""
        
        # Phrases that are definitely not factual claims
        self.non_claim_phrases = {
            # Greetings & farewells
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'good night', 'greetings', 'welcome', 'goodbye', 'bye', 'farewell',
            'see you', 'see you later', 'take care', 'have a good day',
            
            # Thanks & acknowledgments
            'thank you', 'thanks', 'thank you very much', 'thanks very much',
            'thank you so much', 'much appreciated', 'appreciate it',
            'you\'re welcome', 'no problem', 'my pleasure', 'anytime',
            
            # Pleasantries & responses
            'please', 'excuse me', 'sorry', 'apologies', 'pardon me',
            'okay', 'ok', 'alright', 'sure', 'yes', 'no', 'yeah', 'nope',
            'uh huh', 'mm hmm', 'got it', 'understood', 'i see', 'right',
            
            # Conversational fillers
            'well', 'so', 'now', 'then', 'anyway', 'you know', 'i mean',
            'basically', 'actually', 'literally', 'like', 'um', 'uh', 'er', 'ah',
            
            # Ceremonial/formal openings
            'ladies and gentlemen', 'distinguished guests', 'dear friends',
            'my fellow americans', 'folks'
        }
        
        # Subjective opinion indicators that should be filtered out
        self.opinion_indicators = {
            # Explicit opinion markers
            'i think', 'i believe', 'i feel', 'in my opinion', 'it seems to me',
            'i suppose', 'i guess', 'i assume', 'personally', 'from my perspective',
            
            # Value judgments (these make claims subjective)
            'good', 'bad', 'great', 'terrible', 'horrible', 'wonderful', 'amazing',
            'awful', 'fantastic', 'excellent', 'poor', 'brilliant', 'stupid',
            'smart', 'dumb', 'wise', 'foolish', 'right', 'wrong', 'correct', 'incorrect',
            'best', 'worst', 'better', 'worse', 'superior', 'inferior',
            
            # Emotional characterizations
            'disaster', 'catastrophe', 'crisis', 'success', 'failure', 'triumph',
            'victory', 'defeat', 'embarrassment', 'shame', 'pride', 'honor',
            
            # Subjective descriptors
            'beautiful', 'ugly', 'attractive', 'disgusting', 'pleasant', 'unpleasant',
            'comfortable', 'uncomfortable', 'exciting', 'boring', 'interesting', 'dull'
        }
        
        # Patterns for statements that are clearly opinions, not facts
        self.opinion_patterns = [
            # Direct opinion statements
            r'\b(is|was|are|were)\s+(good|bad|great|terrible|horrible|wonderful|amazing|awful|fantastic|excellent|poor|brilliant|stupid|smart|dumb|wise|foolish|right|wrong|correct|incorrect|best|worst|better|worse|superior|inferior)\b',
            
            # Value judgments about policy/actions
            r'\b(exactly\s+how\s+to|perfect\s+example\s+of|terrible\s+way\s+to|great\s+way\s+to)\b',
            
            # Characterizations without specific evidence
            r'\b(has\s+shown\s+.*\s+how\s+to)\s+(enact\s+)?(good|bad|great|terrible)\s+(policy|approach|strategy)\b',
            
            # Sweeping judgments
            r'\b(all|every|everyone|nobody|no one)\s+(knows|thinks|believes|feels|understands)\b',
            
            # Subjective assessments of performance
            r'\b(doing\s+a|did\s+a)\s+(good|bad|great|terrible|horrible|wonderful|amazing|awful|fantastic|excellent|poor)\s+job\b',
            
            # Predictions without evidence
            r'\bwill\s+(definitely|certainly|obviously|clearly)\s+(be|become|fail|succeed)\b',
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
            
            logger.info(f"Starting claim extraction from transcript ({len(transcript)} chars)")
            
            # Try AI extraction first if available
            if self.openai_client:
                try:
                    ai_result = self._extract_with_ai(transcript)
                    if ai_result and ai_result.get('claims'):
                        # Apply strict filtering to AI results
                        filtered_claims = []
                        for claim in ai_result['claims']:
                            if self._is_verifiable_factual_claim(claim['text']):
                                filtered_claims.append(claim)
                            else:
                                logger.debug(f"Filtered out opinion/non-claim: {claim['text'][:100]}")
                        
                        ai_result['claims'] = filtered_claims[:self.max_claims]
                        logger.info(f"AI extraction: {len(filtered_claims)} valid claims found")
                        return ai_result
                except Exception as e:
                    logger.error(f"AI extraction failed: {e}")
            
            # Fallback to pattern-based extraction
            pattern_result = self._extract_with_patterns(transcript)
            logger.info(f"Pattern extraction: {len(pattern_result['claims'])} claims found")
            return pattern_result
            
        except Exception as e:
            logger.error(f"Error extracting claims: {e}")
            return {
                'claims': [],
                'speakers': [],
                'topics': [],
                'extraction_method': 'error'
            }
    
    def _extract_with_ai(self, transcript: str) -> Optional[Dict]:
        """Use AI to extract claims with enhanced filtering"""
        try:
            # Limit transcript length for API
            max_length = 8000
            if len(transcript) > max_length:
                transcript = transcript[:max_length] + "..."
            
            prompt = f"""Extract ONLY verifiable factual claims from this transcript. Be extremely selective.

INCLUDE only statements that:
- Make specific, objective claims about events, statistics, or facts
- Can be verified through documentation, data, or evidence  
- State concrete actions that happened or will happen
- Include specific numbers, dates, names, or measurable outcomes
- Make definitive claims about policies, laws, or documented events

EXCLUDE all of the following:
- Pure opinions ("Texas has shown how to enact bad policy")
- Value judgments ("good", "bad", "great", "terrible", "disaster", "success")
- Subjective characterizations ("horrible", "wonderful", "brilliant", "stupid")
- Statements starting with "I think", "I believe", "It seems"
- Greetings, thanks, pleasantries ("Hello", "Thank you", "Good morning")
- Questions of any kind
- Future predictions without specific evidence
- Sweeping generalizations without data
- Emotional assessments ("embarrassing", "shameful", "proud")
- Conversational fillers ("Well", "You know", "I mean")
- Ceremonial language ("Ladies and gentlemen")

Examples of what TO include:
- "Unemployment rose to 7.2% in March"
- "The Senate passed H.R. 1234 with 67 votes"
- "We allocated $50 billion for infrastructure"
- "China exported 2.3 million tons of steel last year"

Examples of what NOT to include:
- "Texas has shown how to enact bad policy" (opinion/characterization)
- "This is a disaster" (subjective judgment)
- "We're doing a great job" (opinion)
- "Everyone knows this is wrong" (sweeping generalization)

Only extract statements that a fact-checker could verify with specific evidence. When in doubt, exclude it.

Format as JSON: [{{"text": "exact claim", "speaker": "name", "reason": "why this is verifiable"}}]

Transcript:
{transcript}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4" if getattr(self.config, 'USE_GPT4', False) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a strict fact-checker's assistant. Only extract claims that can be objectively verified. Reject opinions, value judgments, and subjective statements completely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Lower temperature for more consistent results
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
                        logger.warning("No JSON found in AI response")
                        return None
                        
                # Process claims with additional validation
                processed_claims = []
                speakers = set()
                
                for claim in claims_data:
                    if isinstance(claim, dict) and claim.get('text'):
                        text = claim['text'].strip()
                        speaker = claim.get('speaker', 'Unknown').strip()
                        
                        # Double-check with our strict validation
                        if self._is_verifiable_factual_claim(text):
                            processed_claims.append({
                                'text': text,
                                'speaker': speaker,
                                'context': claim.get('context', ''),
                                'reason': claim.get('reason', '')
                            })
                            if speaker and speaker != 'Unknown':
                                speakers.add(speaker)
                        else:
                            logger.debug(f"AI extracted but filtered: {text}")
                
                return {
                    'claims': processed_claims[:self.max_claims],
                    'speakers': list(speakers),
                    'topics': self._extract_topics(transcript),
                    'extraction_method': 'ai_enhanced'
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                return None
            
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return None
    
    def _extract_with_patterns(self, transcript: str) -> Dict:
        """Extract claims using pattern matching with strict filtering"""
        claims = []
        speakers = set()
        
        # Split into sentences
        sentences = self._split_into_sentences(transcript)
        logger.info(f"Split transcript into {len(sentences)} sentences")
        
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
            
            # Apply strict validation
            if self._is_verifiable_factual_claim(sentence):
                claims.append({
                    'text': sentence,
                    'speaker': current_speaker,
                    'context': ''
                })
        
        logger.info(f"Pattern matching found {len(claims)} valid claims")
        
        return {
            'claims': claims[:self.max_claims],
            'speakers': list(speakers),
            'topics': self._extract_topics(transcript),
            'extraction_method': 'pattern_enhanced'
        }
    
    def _is_verifiable_factual_claim(self, sentence: str) -> bool:
        """Strict validation: only allow genuinely verifiable factual claims"""
        if not sentence or len(sentence.strip()) < 10:
            return False
        
        sentence_clean = sentence.strip().lower()
        
        # First, check if it's a basic non-claim (greetings, etc.)
        if not self._is_valid_claim(sentence):
            return False
        
        # Check for opinion indicators - these disqualify the claim
        for indicator in self.opinion_indicators:
            if indicator in sentence_clean:
                return False
        
        # Check for opinion patterns
        for pattern in self.opinion_patterns:
            if re.search(pattern, sentence_clean):
                logger.debug(f"Opinion pattern matched: {pattern} in '{sentence_clean[:50]}...'")
                return False
        
        # Additional opinion checks
        # Statements that characterize something as good/bad without specific metrics
        if re.search(r'\b(has\s+shown|have\s+shown).*\b(how\s+to)\b', sentence_clean):
            if re.search(r'\b(good|bad|great|terrible|perfect|awful|excellent|poor)\b', sentence_clean):
                return False
        
        # Reject pure characterizations without specific facts
        characterization_patterns = [
            r'^(this|that|it)\s+is\s+(a\s+)?(disaster|catastrophe|crisis|success|failure|triumph|embarrassment)',
            r'\bis\s+(completely|totally|absolutely)\s+(wrong|right|false|true)',
            r'\b(cannot|can\'t)\s+manage\b.*(?!specific\s+data|evidence|numbers)',
        ]
        
        for pattern in characterization_patterns:
            if re.search(pattern, sentence_clean):
                return False
        
        # Now check for factual indicators
        factual_indicators = [
            # Specific numbers and statistics
            r'\b\d+\.?\d*\s*(%|percent|million|billion|thousand)\b',
            r'\$\d+',
            r'\b\d+\s*(votes?|people|jobs|cases|deaths|births)\b',
            
            # Dates and time periods
            r'\b(19|20)\d{2}\b',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d+',
            r'\bin\s+(19|20)\d{2}\b',
            r'\bsince\s+(19|20)\d{2}\b',
            
            # Specific policy/legal references
            r'\b(h\.r\.|s\.|bill|act|amendment)\s*\d+',
            r'\b(executive\s+order|regulation|statute|code)\s+\d+',
            r'\b(section|title|chapter)\s+\d+',
            
            # Specific organizations and official bodies
            r'\b(department\s+of|office\s+of|bureau\s+of|agency\s+of)\b',
            r'\b(congress|senate|house)\s+(passed|voted|approved|rejected)',
            r'\b(supreme\s+court|district\s+court|appeals\s+court)\b',
            
            # Measurable actions and outcomes
            r'\b(increased|decreased|rose|fell|gained|lost|dropped)\s+(by\s+)?\d+',
            r'\b(allocated|spent|invested|cut|reduced)\s+\$?\d+',
            r'\b(signed|vetoed|passed|failed|approved|rejected)\b.*\b(bill|law|agreement|treaty)\b',
            
            # Specific geographical or institutional references
            r'\b(state\s+of|city\s+of|university\s+of|bank\s+of)\s+[A-Z][a-z]+',
            r'\b[A-Z][a-z]+\s+(university|college|hospital|corporation|company)\b',
        ]
        
        # Must have at least one factual indicator
        has_factual_indicator = any(re.search(pattern, sentence_clean) for pattern in factual_indicators)
        
        if not has_factual_indicator:
            # Check for proper nouns (people, places, organizations) with action verbs
            capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence)
            action_verbs = re.search(r'\b(said|announced|declared|signed|voted|passed|failed|won|lost|created|built|destroyed|implemented|launched|introduced|proposed)\b', sentence_clean)
            
            if len(capitalized_words) >= 2 and action_verbs:
                has_factual_indicator = True
        
        if not has_factual_indicator:
            return False
        
        # Additional validation: must be substantial claim
        words = sentence_clean.split()
        if len(words) < 6:
            return False
        
        # Must have a clear subject-verb-object structure for factual claims
        has_verb = any(verb in sentence_clean for verb in [
            'is', 'are', 'was', 'were', 'has', 'have', 'had', 'will', 'would', 'can', 'could',
            'passed', 'failed', 'signed', 'vetoed', 'announced', 'said', 'declared', 'created',
            'increased', 'decreased', 'rose', 'fell', 'gained', 'lost', 'allocated', 'spent'
        ])
        
        if not has_verb:
            return False
        
        # Final check: reject if it's just a characterization
        if re.search(r'^[^.]*\b(is|are|was|were)\s+(just|simply|merely|only)\s+', sentence_clean):
            return False
        
        return True
    
    def _is_valid_claim(self, sentence: str) -> bool:
        """Basic validation - filter out obvious non-claims"""
        if not sentence:
            return False
        
        sentence_clean = sentence.strip().lower()
        
        # Check length - too short is likely not a claim
        if len(sentence.split()) < 4:
            return False
        
        # Skip questions
        if sentence.strip().endswith('?'):
            return False
        
        # Check if entire sentence is a non-claim phrase
        if sentence_clean in self.non_claim_phrases:
            return False
        
        # Check if it starts with non-claim phrases
        for phrase in self.non_claim_phrases:
            if sentence_clean.startswith(phrase + ' ') or sentence_clean == phrase:
                return False
        
        # Skip pure conversational elements
        conversational_only = [
            r'^(well|so|now|then|anyway|however)\s*[,.]?\s*$',
            r'^(you know|i mean|basically|actually|literally)\s*[,.]?\s*$',
            r'^(um|uh|er|ah|oh)\s*[,.]?\s*$',
        ]
        
        for pattern in conversational_only:
            if re.match(pattern, sentence_clean):
                return False
        
        return True
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Remove timestamps and other noise
        text = re.sub(r'\[\d{1,2}:\d{2}(:\d{2})?\]', '', text)
        text = re.sub(r'\(\d{1,2}:\d{2}(:\d{2})?\)', '', text)
        text = re.sub(r'\[APPLAUSE\]|\[LAUGHTER\]|\[MUSIC\]', '', text, flags=re.IGNORECASE)
        
        # Replace line breaks with spaces
        text = re.sub(r'\n+', ' ', text)
        
        # Handle abbreviations
        text = re.sub(r'\b(Mr|Mrs|Dr|Ms|Prof|Sr|Jr|U\.S|etc)\.\s*', r'\1<PERIOD> ', text)
        
        # Split on sentence endings
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Restore periods in abbreviations
        sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences]
        
        # Filter out very short or empty sentences
        return [s for s in sentences if s and len(s) > 15]
    
    def _extract_topics(self, transcript: str) -> List[str]:
        """Extract main topics from transcript"""
        topics = []
        transcript_lower = transcript.lower()
        
        topic_keywords = {
            'economy': ['economy', 'jobs', 'unemployment', 'inflation', 'taxes', 'budget', 'deficit', 'gdp', 'economic'],
            'healthcare': ['healthcare', 'health care', 'insurance', 'medicare', 'medicaid', 'obamacare', 'medical'],
            'immigration': ['immigration', 'border', 'immigrants', 'citizenship', 'deportation', 'asylum', 'migrant'],
            'education': ['education', 'schools', 'students', 'teachers', 'college', 'university', 'tuition', 'educational'],
            'climate': ['climate', 'environment', 'energy', 'pollution', 'renewable', 'carbon', 'emissions', 'environmental'],
            'crime': ['crime', 'police', 'safety', 'violence', 'criminal', 'justice', 'prison', 'law enforcement'],
            'foreign policy': ['china', 'russia', 'war', 'military', 'nato', 'foreign', 'international', 'diplomacy'],
            'covid-19': ['covid', 'coronavirus', 'pandemic', 'vaccine', 'mask', 'lockdown', 'quarantine'],
            'elections': ['election', 'voting', 'campaign', 'ballot', 'voter', 'candidate', 'electoral'],
            'infrastructure': ['infrastructure', 'roads', 'bridges', 'broadband', 'transportation', 'transit'],
            'technology': ['technology', 'tech', 'internet', 'cyber', 'ai', 'artificial intelligence', 'digital'],
            'trade': ['trade', 'tariff', 'import', 'export', 'nafta', 'treaty', 'commerce', 'trade deal']
        }
        
        for topic, keywords in topic_keywords.items():
            keyword_count = sum(1 for keyword in keywords if keyword in transcript_lower)
            if keyword_count >= 2:  # Require at least 2 related keywords
                topics.append(topic)
        
        return topics[:5]  # Limit to top 5 topics
