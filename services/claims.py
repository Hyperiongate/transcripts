"""
Enhanced Claims Extraction Service with Better Context
"""
import re
import logging
from typing import List, Dict, Tuple, Optional
import json
from config import Config

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Enhanced claim extractor that provides full context"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        self.openai_client = None
        self.use_gpt4 = False  # Will be set based on config
        
        if openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized for claims extraction")
                
                # Check if GPT-4 is available/configured
                try:
                    from config import Config
                    self.use_gpt4 = Config.USE_GPT4 if hasattr(Config, 'USE_GPT4') else False
                except:
                    self.use_gpt4 = False
                    
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
    
    def extract_claims(self, transcript: str, max_claims: int = 50) -> List[Dict]:
        """
        Extract claims with full context from transcript
        
        Returns list of dictionaries with:
        - text: The complete claim
        - context: Surrounding context
        - speaker: Who made the claim
        - confidence: How confident we are this is a verifiable claim
        """
        if not transcript:
            return []
        
        # First, identify the speakers and context
        speakers, topics = self.extract_context(transcript)
        
        # Use enhanced AI if available, otherwise use pattern matching
        if self.openai_client:
            claims = self._extract_claims_with_enhanced_ai(transcript, speakers, max_claims)
        else:
            claims = self._extract_claims_with_patterns(transcript, speakers)
        
        # Ensure we have full claims, not snippets
        enhanced_claims = []
        for claim in claims[:max_claims]:
            if isinstance(claim, dict):
                # Ensure we have the full claim text
                if len(claim.get('text', '')) < 50 and 'context' in claim:
                    # This might be a snippet, try to expand it
                    claim['text'] = self._expand_claim(claim['text'], claim.get('context', ''), transcript)
                enhanced_claims.append(claim)
            else:
                # Convert string claims to dict format
                enhanced_claims.append({
                    'text': str(claim),
                    'speaker': speakers[0] if speakers else 'Unknown',
                    'confidence': 70
                })
        
        return enhanced_claims
    
    def extract_context(self, transcript: str) -> Tuple[List[str], List[str]]:
        """Extract speakers and topics from transcript"""
        speakers = []
        topics = []
        
        # Look for speaker patterns
        speaker_patterns = [
            r'(?:President|Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][A-Z]+):\s*',  # ALL CAPS speaker labels
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*:\s*',  # Name: format
        ]
        
        transcript_lower = transcript.lower()
        
        # Specific speaker identification with more robust patterns
        if any(term in transcript_lower for term in ['trump:', 'donald trump', 'president trump', 'former president trump']):
            speakers.append('Donald Trump')
        
        if any(term in transcript_lower for term in ['harris:', 'kamala harris', 'vice president harris', 'madam vice president']):
            speakers.append('Kamala Harris')
        
        # Check for debate context - CRITICAL FIX
        if 'debate' in transcript_lower or 'moderator' in transcript_lower:
            # If both names appear in the transcript, it's likely their debate
            if ('trump' in transcript_lower or 'donald' in transcript_lower) and ('harris' in transcript_lower or 'kamala' in transcript_lower):
                if 'Donald Trump' not in speakers:
                    speakers.append('Donald Trump')
                if 'Kamala Harris' not in speakers:
                    speakers.append('Kamala Harris')
                topics.append('Presidential Debate - September 10, 2024')
        
        # Try pattern matching for other speakers
        for pattern in speaker_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                if isinstance(match, str) and match not in speakers:
                    # Clean up the match
                    speaker = match.strip()
                    if len(speaker) > 2 and len(speaker) < 50:  # Reasonable name length
                        speakers.append(speaker)
        
        # Extract topics
        topic_keywords = {
            'economy': ['economy', 'inflation', 'jobs', 'unemployment', 'gdp', 'recession'],
            'immigration': ['immigration', 'border', 'migrants', 'asylum', 'deportation'],
            'healthcare': ['healthcare', 'medicare', 'medicaid', 'obamacare', 'insurance'],
            'foreign policy': ['ukraine', 'russia', 'china', 'nato', 'military', 'israel'],
            'crime': ['crime', 'violence', 'police', 'safety', 'murder', 'shooting'],
            'abortion': ['abortion', 'roe', 'reproductive', 'pro-life', 'pro-choice'],
            'climate': ['climate', 'environment', 'renewable', 'emissions', 'paris'],
            'education': ['education', 'schools', 'teachers', 'student loans']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_lower for keyword in keywords):
                topics.append(topic)
        
        # Remove duplicates while preserving order
        speakers = list(dict.fromkeys(speakers))
        topics = list(dict.fromkeys(topics))
        
        return speakers, topics
    
    def _extract_claims_with_enhanced_ai(self, transcript: str, speakers: List[str], max_claims: int) -> List[Dict]:
        """Enhanced AI claim extraction with better context understanding"""
        
        if not self.openai_client:
            return self._extract_claims_with_patterns(transcript, speakers)
        
        try:
            # Use GPT-4 for better accuracy if available
            model = "gpt-4" if self.use_gpt4 else "gpt-3.5-turbo"
            
            # Prepare speaker context
            speaker_context = ""
            if speakers:
                speaker_context = f"Speakers identified: {', '.join(speakers)}\n"
                if 'Donald Trump' in speakers and 'Kamala Harris' in speakers:
                    speaker_context += "Context: This appears to be from the Trump-Harris presidential debate on September 10, 2024.\n"
            
            # Split transcript into manageable chunks if too long
            max_chars = 6000
            if len(transcript) > max_chars:
                # Process in chunks
                chunks = []
                words = transcript.split()
                current_chunk = []
                current_length = 0
                
                for word in words:
                    current_length += len(word) + 1
                    if current_length > max_chars:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = [word]
                        current_length = len(word)
                    else:
                        current_chunk.append(word)
                
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
            else:
                chunks = [transcript]
            
            all_claims = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)} with AI")
                
                prompt = f"""
                You are an expert fact-checker analyzing a political transcript. Extract factual claims that can be verified.
                
                {speaker_context}
                
                IMPORTANT INSTRUCTIONS:
                1. Extract COMPLETE claims with full context - not fragments
                2. Include WHO said it (speaker attribution)
                3. Preserve exact wording - do not paraphrase
                4. Focus on verifiable factual assertions, not opinions
                5. Include claims about:
                   - Statistics, numbers, percentages
                   - Historical events or actions
                   - Policy positions or voting records
                   - Comparisons or rankings
                   - Statements about what did or didn't happen
                
                For each claim, assess:
                - Is this a factual assertion or opinion?
                - Can this be verified with evidence?
                - Is the speaker making a specific, checkable claim?
                
                DO NOT include:
                - Future predictions or promises
                - Personal feelings or beliefs
                - Vague generalizations
                - Rhetorical questions
                
                Transcript chunk {i+1}/{len(chunks)}:
                {chunk}
                
                Return a JSON array with up to {max_claims // len(chunks)} claims:
                [
                    {{
                        "text": "Complete claim exactly as stated",
                        "speaker": "Speaker name",
                        "context": "Relevant surrounding context",
                        "type": "statistic|historical|policy|comparison|action",
                        "confidence": 0-100
                    }}
                ]
                
                Ensure each claim is a complete sentence or thought, not a fragment.
                """
                
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a precise fact-checking assistant. Extract complete, verifiable claims while maintaining exact wording and full context."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,  # Lower temperature for more consistent extraction
                    max_tokens=3000
                )
                
                content = response.choices[0].message.content
                
                # Parse JSON response
                try:
                    # Find JSON array in response
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        claims_data = json.loads(json_match.group())
                        
                        # Validate and enhance claims
                        for claim in claims_data:
                            if isinstance(claim, dict) and claim.get('text'):
                                # Ensure we have complete sentences
                                claim_text = claim['text'].strip()
                                
                                # Skip if too short
                                if len(claim_text) < 20:
                                    continue
                                
                                # Ensure it ends with punctuation
                                if claim_text and claim_text[-1] not in '.!?':
                                    claim_text += '.'
                                
                                all_claims.append({
                                    'text': claim_text,
                                    'speaker': claim.get('speaker', speakers[0] if speakers else 'Unknown'),
                                    'context': claim.get('context', ''),
                                    'type': claim.get('type', 'general'),
                                    'confidence': min(max(claim.get('confidence', 75), 0), 100)
                                })
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON: {e}")
                    # Try to parse as structured text
                    parsed_claims = self._parse_structured_claims(content, speakers)
                    all_claims.extend(parsed_claims)
            
            logger.info(f"AI extracted {len(all_claims)} total claims")
            return all_claims
                
        except Exception as e:
            logger.error(f"Enhanced AI extraction error: {str(e)}")
        
        # Fallback to pattern-based extraction
        return self._extract_claims_with_patterns(transcript, speakers)
    
    def _parse_structured_claims(self, content: str, speakers: List[str]) -> List[Dict]:
        """Parse structured text response from AI"""
        claims = []
        
        # Look for numbered claims
        claim_pattern = re.compile(r'(?:^|\n)(?:\d+\.|\-|\*)\s*(?:\[([^\]]+)\]:\s*)?(.+?)(?=\n(?:\d+\.|\-|\*)|$)', re.MULTILINE | re.DOTALL)
        
        matches = claim_pattern.findall(content)
        for match in matches:
            speaker = match[0] if match[0] else (speakers[0] if speakers else 'Unknown')
            claim_text = match[1].strip()
            
            # Skip if too short
            if len(claim_text) < 20:
                continue
            
            # Remove any "CONTEXT:" or similar prefixes from the claim
            claim_text = re.sub(r'^(?:CLAIM|CONTEXT|EXPLANATION):\s*', '', claim_text, flags=re.IGNORECASE)
            
            claims.append({
                'text': claim_text,
                'speaker': speaker,
                'context': '',
                'confidence': 75
            })
        
        return claims
    
    def _extract_claims_with_patterns(self, transcript: str, speakers: List[str]) -> List[Dict]:
        """Extract claims using pattern matching"""
        claims = []
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', transcript)
        
        # Patterns that indicate factual claims
        claim_patterns = [
            (r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:percent|%)', 'statistic'),
            (r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|billion|thousand)', 'number'),
            (r'(?:increased?|decreased?|rose|fell|grew)\s+(?:by\s+)?(\d+)', 'change'),
            (r'(?:never|always|every|none|all)\s+', 'absolute'),
            (r'(?:will|going to|plan to|intend to)\s+', 'promise'),
            (r'(?:was|were|has been|have been)\s+', 'historical'),
            (r'(?:more than|less than|fewer than|greater than)\s+', 'comparison'),
            (r'(?:highest|lowest|biggest|smallest|first|last)\s+', 'superlative'),
            (r'(?:trump|harris)\s+(?:said|did|voted|signed|passed)', 'action'),
        ]
        
        current_speaker = speakers[0] if speakers else 'Unknown'
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 20:  # Too short to be a meaningful claim
                continue
            
            # Update current speaker if found
            sentence_lower = sentence.lower()
            for speaker in speakers:
                if speaker.lower() in sentence_lower:
                    current_speaker = speaker
                    break
            
            # Check if this sentence contains a claim
            is_claim = False
            claim_type = None
            confidence = 60
            
            for pattern, ptype in claim_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    is_claim = True
                    claim_type = ptype
                    confidence = 75
                    break
            
            # Special patterns for debate claims
            if not is_claim:
                if any(phrase in sentence_lower for phrase in ['never happened', 'didn\'t happen', 'did not happen', 'false claim']):
                    is_claim = True
                    claim_type = 'denial'
                    confidence = 80
                elif any(phrase in sentence_lower for phrase in ['we did', 'i did', 'we accomplished', 'i signed']):
                    is_claim = True
                    claim_type = 'achievement'
                    confidence = 75
            
            if is_claim:
                # Get context (previous and next sentence if available)
                context_parts = []
                if i > 0:
                    context_parts.append(sentences[i-1].strip())
                if i < len(sentences) - 1:
                    context_parts.append(sentences[i+1].strip())
                
                full_context = ' '.join(context_parts)
                
                # Ensure we capture the full sentence, not fragments
                full_sentence = sentence
                
                # If the sentence seems incomplete, try to expand it
                if not sentence.endswith('.') and i < len(sentences) - 1:
                    # Might be a fragment, include next part
                    full_sentence = sentence + ' ' + sentences[i+1] if i+1 < len(sentences) else sentence
                
                claims.append({
                    'text': full_sentence,
                    'speaker': current_speaker,
                    'context': full_context,
                    'type': claim_type,
                    'confidence': confidence
                })
        
        return claims
    
    def _expand_claim(self, snippet: str, context: str, transcript: str) -> str:
        """Expand a claim snippet to include the full statement"""
        if not snippet or not transcript:
            return snippet
        
        # Find the snippet in the transcript
        snippet_lower = snippet.lower()
        transcript_lower = transcript.lower()
        
        pos = transcript_lower.find(snippet_lower)
        if pos == -1:
            return snippet
        
        # Find sentence boundaries
        start = pos
        end = pos + len(snippet)
        
        # Expand to sentence start
        while start > 0 and transcript[start-1] not in '.!?':
            start -= 1
            if start > 0 and transcript[start-1] in '.!?':
                break
        
        # Skip whitespace at start
        while start < len(transcript) and transcript[start] in ' \n\t':
            start += 1
        
        # Expand to sentence end
        while end < len(transcript) and transcript[end] not in '.!?':
            end += 1
        
        # Include the ending punctuation
        if end < len(transcript) and transcript[end] in '.!?':
            end += 1
        
        full_claim = transcript[start:end].strip()
        
        # Clean up
        full_claim = re.sub(r'\s+', ' ', full_claim)
        
        # If we got a good expansion, use it
        if len(full_claim) > len(snippet) and len(full_claim) < 500:
            return full_claim
        else:
            return snippet
