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

class ClaimExtractor:
    """Advanced claims extraction with AI-powered filtering"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized for claims extraction")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            logger.warning("spaCy model not loaded. Some features may be limited.")
            self.nlp = None
        
        # Configuration
        self.use_gpt4 = True  # Use GPT-4 for better extraction
        self.use_ai_extraction = True  # Use AI as primary extraction method
        
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
        
        # Factual indicators
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
                r'(?:first|last|only)',
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
        
        # Use AI extraction if available and enabled
        if self.openai_client and self.use_ai_extraction:
            return self._extract_claims_with_ai(transcript, max_claims)
        else:
            # Fallback to pattern-based extraction
            return self._extract_claims_pattern_based(transcript, max_claims)
    
    def _extract_claims_with_ai(self, transcript: str, max_claims: int) -> List[Dict]:
        """Extract claims using GPT-4"""
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            # Split transcript into chunks if too long
            max_chars = 8000  # Leave room for prompt
            chunks = []
            if len(transcript) > max_chars:
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
                
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": """You are an expert at extracting verifiable factual claims from transcripts.
                        
Extract ONLY statements that:
- Make specific factual assertions that can be verified
- Include statistics, numbers, or measurable claims
- Reference historical events or specific incidents
- Make claims about policies, laws, or regulations
- Assert cause-and-effect relationships
- Compare or rank things

DO NOT extract:
- Opinions or beliefs
- Vague generalizations
- Greetings or pleasantries
- Questions
- Future predictions or promises
- Personal anecdotes without factual claims"""},
                        {"role": "user", "content": f"""Extract all verifiable factual claims from this transcript.

Return a JSON array where each item has:
{{
    "claim": "the exact claim text",
    "context": "brief context if needed",
    "confidence": 0-100 (how likely this is a verifiable claim),
    "category": "statistics/historical/policy/comparison/other"
}}

Transcript:
{chunk}

Extract up to {max_claims // len(chunks)} claims from this section."""}
                    ],
                    temperature=0.3,
                    max_tokens=4000
                )
                
                # Parse response
                try:
                    claims_data = json.loads(response.choices[0].message.content)
                    if isinstance(claims_data, list):
                        for claim_info in claims_data:
                            if isinstance(claim_info, dict) and 'claim' in claim_info:
                                all_claims.append({
                                    'text': claim_info['claim'],
                                    'context': claim_info.get('context', ''),
                                    'confidence': claim_info.get('confidence', 80),
                                    'category': claim_info.get('category', 'other'),
                                    'ai_extracted': True
                                })
                except:
                    logger.error("Failed to parse AI response for claims")
            
            # Sort by confidence and limit
            all_claims.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            return all_claims[:max_claims]
            
        except Exception as e:
            logger.error(f"AI claims extraction error: {e}")
            # Fallback to pattern-based
            return self._extract_claims_pattern_based(transcript, max_claims)
    
    def _extract_claims_pattern_based(self, transcript: str, max_claims: int) -> List[Dict]:
        """Original pattern-based extraction as fallback"""
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
                    'word_count': len(claim.split()),
                    'ai_extracted': False
                })
        
        # Step 4: Sort by score and take top claims
        scored_claims.sort(key=lambda x: x['score'], reverse=True)
        top_claims = scored_claims[:max_claims]
        
        # Step 5: Final cleanup
        final_claims = []
        for claim_data in top_claims:
            cleaned = self._clean_claim(claim_data['text'])
            if cleaned:
                claim_data['text'] = cleaned
                final_claims.append(claim_data)
        
        logger.info(f"Extracted {len(final_claims)} factual claims from {len(sentences)} sentences")
        return final_claims
    
    def extract_context(self, transcript: str) -> Tuple[List[str], List[str]]:
        """Extract speakers and topics from transcript using AI if available"""
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract speakers and main topics from transcripts."},
                        {"role": "user", "content": f"""From this transcript, extract:
1. All speaker names mentioned
2. Main topics discussed

Transcript excerpt:
{transcript[:2000]}

Return as JSON: {{"speakers": [...], "topics": [...]}}"""}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                
                try:
                    data = json.loads(response.choices[0].message.content)
                    return data.get('speakers', []), data.get('topics', [])
                except:
                    pass
            except:
                pass
        
        # Fallback to pattern-based extraction
        speakers = []
        topics = []
        
        # Look for speaker patterns
        lines = transcript.split('\n')
        speaker_patterns = [
            r'^([A-Z][A-Z\s\.]+):',  # ALL CAPS:
            r'^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]',  # [Speaker Name]
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?):',  # Speaker Name:
        ]
        
        for line in lines[:50]:  # Check first 50 lines
            for pattern in speaker_patterns:
                match = re.match(pattern, line)
                if match:
                    speaker = match.group(1).strip()
                    if speaker not in speakers and len(speaker) < 50:
                        speakers.append(speaker)
        
        # Extract topics based on keywords
        text_lower = transcript.lower()
        for topic in self.factual_topics:
            if topic in text_lower:
                topics.append(topic)
        
        return speakers, topics
    
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
            indicator in text_lower for indicator in ['did you know', 'isn\'t it true']
        ):
            return True
        
        # Check for personal pronouns at start
        if re.match(r'^(i|we|my|our)\s+', text_lower) and not any(
            phrase in text_lower for phrase in ['i voted', 'we passed', 'i signed', 'we achieved']
        ):
            return True
        
        return False
    
    def _score_claim(self, claim: str) -> float:
        """Score a claim based on factual indicators"""
        score = 0.0
        claim_lower = claim.lower()
        
        # Check factual indicators
        for category, patterns in self.factual_indicators.items():
            for pattern in patterns:
                if re.search(pattern, claim_lower):
                    score += 2.0
                    break
        
        # Check for numbers
        numbers = re.findall(r'\b\d+(?:,\d+)*(?:\.\d+)?\b', claim)
        score += min(len(numbers) * 0.5, 2.0)
        
        # Check for factual topics
        for topic in self.factual_topics:
            if topic in claim_lower:
                score += 1.0
        
        # Check for specific factual words
        factual_words = ['percent', 'million', 'billion', 'increase', 'decrease', 
                         'rate', 'data', 'study', 'report', 'according']
        for word in factual_words:
            if word in claim_lower:
                score += 0.5
        
        # Penalize vague language
        vague_words = ['some', 'many', 'few', 'several', 'various', 'certain']
        for word in vague_words:
            if word in claim_lower:
                score -= 0.5
        
        # Penalize if too short or too long
        word_count = len(claim.split())
        if word_count < 8:
            score -= 1.0
        elif word_count > 50:
            score -= 0.5
        
        return max(score, 0)
    
    def _get_claim_indicators(self, claim: str) -> List[str]:
        """Get list of indicator categories present in claim"""
        indicators = []
        claim_lower = claim.lower()
        
        for category, patterns in self.factual_indicators.items():
            for pattern in patterns:
                if re.search(pattern, claim_lower):
                    indicators.append(category)
                    break
        
        return indicators
    
    def _clean_claim(self, claim: str) -> str:
        """Clean and normalize claim text"""
        # Remove extra whitespace
        claim = ' '.join(claim.split())
        
        # Remove speaker labels if still present
        claim = re.sub(r'^[A-Z][A-Z\s\.]+:\s*', '', claim)
        claim = re.sub(r'^\[[^\]]+\]\s*', '', claim)
        
        # Ensure ends with period
        if claim and not claim[-1] in '.!?':
            claim += '.'
        
        # Capitalize first letter
        if claim:
            claim = claim[0].upper() + claim[1:]
        
        return claim
