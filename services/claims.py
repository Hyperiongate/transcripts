"""
Enhanced Claims Extraction Service with Better Context
"""
import re
import logging
from typing import List, Dict, Tuple, Optional
import openai
from config import Config

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Enhanced claim extractor that provides full context"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        if openai_api_key:
            openai.api_key = openai_api_key
    
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
        
        # Use AI if available, otherwise use pattern matching
        if self.openai_api_key:
            claims = self._extract_claims_with_ai(transcript, speakers, max_claims)
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
        
        for pattern in speaker_patterns:
            matches = re.findall(pattern, transcript)
            speakers.extend([m for m in matches if isinstance(m, str)])
        
        # Specific speaker identification
        transcript_lower = transcript.lower()
        
        # Check for Trump
        if any(term in transcript_lower for term in ['trump', 'donald trump', 'president trump', 'former president']):
            speakers.append('Donald Trump')
        
        # Check for Harris
        if any(term in transcript_lower for term in ['harris', 'kamala harris', 'vice president harris']):
            speakers.append('Kamala Harris')
        
        # Check for debate context
        if 'debate' in transcript_lower:
            if 'trump' in transcript_lower and 'harris' in transcript_lower:
                if 'Donald Trump' not in speakers:
                    speakers.append('Donald Trump')
                if 'Kamala Harris' not in speakers:
                    speakers.append('Kamala Harris')
                topics.append('Presidential Debate')
        
        # Extract topics
        topic_keywords = {
            'economy': ['economy', 'inflation', 'jobs', 'unemployment', 'gdp'],
            'immigration': ['immigration', 'border', 'migrants', 'asylum'],
            'healthcare': ['healthcare', 'medicare', 'medicaid', 'obamacare'],
            'foreign policy': ['ukraine', 'russia', 'china', 'nato', 'military'],
            'crime': ['crime', 'violence', 'police', 'safety'],
            'abortion': ['abortion', 'roe', 'reproductive', 'pro-life', 'pro-choice']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_lower for keyword in keywords):
                topics.append(topic)
        
        # Remove duplicates while preserving order
        speakers = list(dict.fromkeys(speakers))
        topics = list(dict.fromkeys(topics))
        
        return speakers, topics
    
    def _extract_claims_with_ai(self, transcript: str, speakers: List[str], max_claims: int) -> List[Dict]:
        """Use AI to extract claims"""
        try:
            # Prepare the prompt
            speaker_context = f"The speakers in this transcript are: {', '.join(speakers)}. " if speakers else ""
            
            prompt = f"""
            Extract verifiable factual claims from this transcript. 
            {speaker_context}
            
            For each claim, provide:
            1. The COMPLETE claim (full sentences, not snippets)
            2. Who said it
            3. Any important context
            
            Focus on claims about:
            - Statistics and numbers
            - Historical events
            - Policy positions
            - Comparisons
            - Promises or commitments
            
            Transcript:
            {transcript[:3000]}  # Limit for API
            
            Return up to {max_claims} claims in this format:
            CLAIM 1: [Speaker]: [Complete claim text]
            CONTEXT: [Any necessary context]
            
            Make sure each claim is a complete thought, not a fragment.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying factual claims in political transcripts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            claims = []
            
            # Parse the response
            claim_blocks = content.split('CLAIM')
            for block in claim_blocks[1:]:  # Skip the first empty split
                lines = block.strip().split('\n')
                if lines:
                    # Extract claim text
                    claim_line = lines[0]
                    # Remove the number and colon
                    claim_text = re.sub(r'^\d+:\s*', '', claim_line)
                    
                    # Extract speaker if present
                    speaker_match = re.match(r'\[([^\]]+)\]:\s*(.+)', claim_text)
                    if speaker_match:
                        speaker = speaker_match.group(1)
                        claim_text = speaker_match.group(2)
                    else:
                        speaker = speakers[0] if speakers else 'Unknown'
                    
                    # Extract context if present
                    context = ''
                    for line in lines[1:]:
                        if line.strip().startswith('CONTEXT:'):
                            context = line.replace('CONTEXT:', '').strip()
                            break
                    
                    claims.append({
                        'text': claim_text.strip(),
                        'speaker': speaker,
                        'context': context,
                        'confidence': 85
                    })
            
            return claims
            
        except Exception as e:
            logger.error(f"AI claim extraction error: {str(e)}")
            # Fall back to pattern matching
            return self._extract_claims_with_patterns(transcript, speakers)
    
    def _extract_claims_with_patterns(self, transcript: str, speakers: List[str]) -> List[Dict]:
        """Extract claims using pattern matching"""
        claims = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', transcript)
        
        # Patterns that indicate factual claims
        claim_patterns = [
            (r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:percent|%)', 'statistic'),
            (r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|billion|thousand)', 'number'),
            (r'(?:increased?|decreased?|rose|fell|grew)\s+(?:by\s+)?(\d+)', 'change'),
            (r'(?:never|always|every|none|all)\s+\w+', 'absolute'),
            (r'(?:will|going to|plan to|intend to)\s+\w+', 'promise'),
            (r'(?:was|were|has been|have been)\s+\w+', 'historical'),
            (r'(?:more than|less than|fewer than|greater than)\s+\w+', 'comparison')
        ]
        
        current_speaker = speakers[0] if speakers else 'Unknown'
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 20:  # Too short to be a meaningful claim
                continue
            
            # Check for speaker changes
            for speaker in speakers:
                if speaker in sentence:
                    current_speaker = speaker
                    break
            
            # Check if this sentence contains a claim
            is_claim = False
            claim_type = None
            
            for pattern, ptype in claim_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    is_claim = True
                    claim_type = ptype
                    break
            
            if is_claim:
                # Get context (previous and next sentence if available)
                context_parts = []
                if i > 0:
                    context_parts.append(sentences[i-1].strip())
                context_parts.append(sentence)
                if i < len(sentences) - 1:
                    context_parts.append(sentences[i+1].strip())
                
                full_context = ' '.join(context_parts)
                
                claims.append({
                    'text': sentence,
                    'speaker': current_speaker,
                    'context': full_context,
                    'type': claim_type,
                    'confidence': 70
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
        
        # Expand to sentence end
        while end < len(transcript) and transcript[end] not in '.!?':
            end += 1
        
        # Include the ending punctuation
        if end < len(transcript):
            end += 1
        
        full_claim = transcript[start:end].strip()
        
        # Clean up
        full_claim = re.sub(r'\s+', ' ', full_claim)
        
        return full_claim if len(full_claim) > len(snippet) else snippet
