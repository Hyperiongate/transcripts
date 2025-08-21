"""
Enhanced Claims Extraction Service with AI Integration
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Extract factual claims from transcripts with AI enhancement"""
    
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
        
        # Patterns for identifying factual claims
        self.claim_patterns = [
            # Statistical claims
            r'\b(\d+(?:\.\d+)?)\s*(?:percent|%)\s+(?:of|in|from)',
            r'\b(?:increased?|decreased?|grew|fell|rose|dropped)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:percent|%)?',
            
            # Numerical claims
            r'\b(?:about|approximately|nearly|over|under|more than|less than|at least)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|thousand)',
            
            # Comparative claims
            r'\b(?:more|less|fewer|greater|higher|lower|better|worse)\s+than',
            r'\b(?:the\s+)?(?:most|least|best|worst|highest|lowest|biggest|smallest)',
            
            # Temporal claims
            r'\b(?:since|during|between|from|in)\s+(?:19|20)\d{2}',
            r'\b(?:last|this|next)\s+(?:year|month|week|decade)',
            
            # Definitive statements
            r'\b(?:is|are|was|were|has|have|had)\s+(?:the\s+)?(?:first|last|only|largest|smallest)',
            r'\b(?:always|never|all|none|every|no\s+one)',
            
            # Policy/action claims
            r'\b(?:passed|signed|voted|approved|rejected|banned|allowed)',
            r'\b(?:created|eliminated|increased|decreased|cut|raised)\s+(?:taxes|jobs|spending)',
        ]
        
        # Keywords that indicate factual claims
        self.factual_keywords = [
            'percent', 'million', 'billion', 'increased', 'decreased',
            'doubled', 'tripled', 'record', 'highest', 'lowest',
            'unemployment', 'inflation', 'economy', 'jobs', 'crime',
            'immigration', 'healthcare', 'education', 'taxes',
            'climate', 'temperature', 'emissions', 'energy'
        ]
        
        # Patterns to exclude (opinions, questions, etc.)
        self.exclusion_patterns = [
            r'^\s*(?:i|we)\s+(?:think|believe|feel|hope|wish)',
            r'^\s*(?:in my opinion|personally|honestly)',
            r'\?$',  # Questions
            r'^\s*(?:thank you|hello|good morning|good evening)',
            r'^\s*(?:um|uh|well|so|anyway|basically)',
        ]
    
    def extract(self, transcript: str) -> Dict:
        """Extract claims from transcript"""
        try:
            # Try AI extraction first if available
            if self.openai_client:
                ai_result = self._extract_with_ai(transcript)
                if ai_result and ai_result.get('claims'):
                    return ai_result
            
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
    
    def extract_claims_enhanced(self, transcript: str, use_ai: bool = True) -> List[Dict]:
        """Enhanced claim extraction that returns full sentences"""
        result = self.extract(transcript)
        
        # Convert to expected format
        claims = []
        for claim in result.get('claims', []):
            if isinstance(claim, dict):
                claims.append({
                    'text': claim.get('text', ''),
                    'speaker': claim.get('speaker', 'Unknown'),
                    'context': claim.get('context', '')
                })
            else:
                claims.append({
                    'text': claim,
                    'speaker': 'Unknown',
                    'context': ''
                })
        
        return claims
    
    def _extract_with_ai(self, transcript: str) -> Optional[Dict]:
        """Use AI to extract claims with full context"""
        try:
            # Limit transcript length for API
            transcript_excerpt = transcript[:8000] if len(transcript) > 8000 else transcript
            
            prompt = f"""Extract all factual claims from this transcript that can be fact-checked.

For each claim, provide:
1. The COMPLETE sentence or statement (not just a fragment)
2. The speaker (if identifiable)
3. Important context from surrounding sentences

Focus on:
- Statistical claims (percentages, numbers)
- Historical claims (events, dates)
- Policy claims (laws, regulations)
- Comparative claims (more/less than)
- Definitive statements (first, only, never, always)

Exclude:
- Opinions
- Predictions
- Questions
- Greetings

Return as JSON array with format:
[{{"text": "full claim sentence", "speaker": "name", "context": "relevant context"}}]

Transcript:
{transcript_excerpt}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4" if "gpt-4" in str(self.openai_client) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying factual claims in political speeches and debates."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if content.startswith('['):
                claims_data = json.loads(content)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    claims_data = json.loads(json_match.group())
                else:
                    return None
            
            # Extract speakers and topics
            speakers = list(set(claim.get('speaker', '') for claim in claims_data if claim.get('speaker')))
            topics = self._extract_topics(transcript)
            
            return {
                'claims': claims_data,
                'speakers': [s for s in speakers if s and s != 'Unknown'],
                'topics': topics,
                'extraction_method': 'ai_enhanced'
            }
            
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return None
    
    def _extract_with_patterns(self, transcript: str) -> Dict:
        """Extract claims using pattern matching"""
        claims = []
        speakers = []
        
        # Split into sentences
        sentences = self._split_into_sentences(transcript)
        
        # Extract speaker names
        speaker_pattern = r'^([A-Z][A-Z\s\.]+):|^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]'
        current_speaker = "Unknown"
        
        for sentence in sentences:
            # Check for speaker
            speaker_match = re.match(speaker_pattern, sentence)
            if speaker_match:
                current_speaker = speaker_match.group(1) or speaker_match.group(2)
                if current_speaker not in speakers:
                    speakers.append(current_speaker)
                # Remove speaker label from sentence
                sentence = re.sub(speaker_pattern, '', sentence).strip()
            
            # Skip if matches exclusion patterns
            if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in self.exclusion_patterns):
                continue
            
            # Check if sentence contains factual claim patterns
            is_factual = False
            
            # Check against claim patterns
            for pattern in self.claim_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    is_factual = True
                    break
            
            # Check for factual keywords
            if not is_factual:
                sentence_lower = sentence.lower()
                if any(keyword in sentence_lower for keyword in self.factual_keywords):
                    is_factual = True
            
            # Add if factual and meets length requirements
            if is_factual and 10 < len(sentence.split()) < 100:
                claims.append({
                    'text': sentence.strip(),
                    'speaker': current_speaker,
                    'context': ''
                })
        
        # Extract topics
        topics = self._extract_topics(transcript)
        
        return {
            'claims': claims[:50],  # Limit to 50 claims
            'speakers': speakers,
            'topics': topics,
            'extraction_method': 'pattern_based'
        }
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Remove timestamps
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
        text = re.sub(r'\[\d{2}:\d{2}\]', '', text)
        
        # Basic sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Clean and filter
        cleaned = []
        for sent in sentences:
            sent = sent.strip()
            if sent and len(sent) > 20:
                cleaned.append(sent)
        
        return cleaned
    
    def _extract_topics(self, transcript: str) -> List[str]:
        """Extract main topics from transcript"""
        topics = []
        topic_keywords = {
            'economy': ['economy', 'inflation', 'jobs', 'unemployment', 'gdp', 'recession'],
            'healthcare': ['healthcare', 'medicare', 'medicaid', 'insurance', 'obamacare'],
            'immigration': ['immigration', 'border', 'migrants', 'deportation', 'citizenship'],
            'climate': ['climate', 'environment', 'emissions', 'renewable', 'fossil fuels'],
            'crime': ['crime', 'violence', 'police', 'safety', 'murder', 'theft'],
            'education': ['education', 'schools', 'students', 'teachers', 'college'],
            'foreign policy': ['war', 'military', 'defense', 'nato', 'china', 'russia'],
            'taxes': ['taxes', 'tax cut', 'tax increase', 'irs', 'deduction']
        }
        
        transcript_lower = transcript.lower()
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:5]  # Return top 5 topics
