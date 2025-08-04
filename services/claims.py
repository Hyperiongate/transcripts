"""
Claim extraction service
Identifies and prioritizes factual claims from transcripts
"""
import re
import logging
from typing import List, Dict
from collections import Counter

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Extract and analyze factual claims from text"""
    
    def __init__(self):
        # Claim indicator patterns
        self.statistical_patterns = [
            r'\b\d+\.?\d*\s*(?:percent|%)\b',
            r'\b\d+\.?\d*\s*(?:million|billion|trillion)\b',
            r'\b\d+\s*(?:times|x)\s*(?:more|less|higher|lower)\b',
            r'\b(?:doubled|tripled|quadrupled|increased|decreased)\s*(?:by|to)?\s*\d+',
        ]
        
        self.factual_indicators = [
            'according to', 'studies show', 'research indicates', 'data shows',
            'statistics reveal', 'surveys found', 'reports indicate', 'analysis shows',
            'evidence suggests', 'findings show', 'records show', 'documents reveal'
        ]
        
        self.temporal_indicators = [
            'first', 'last', 'latest', 'newest', 'oldest', 'recently',
            'historically', 'traditionally', 'originally', 'initially',
            'in \d{4}', 'since \d{4}', 'before \d{4}', 'after \d{4}'
        ]
        
        self.comparison_words = [
            'more than', 'less than', 'greater than', 'fewer than',
            'higher than', 'lower than', 'compared to', 'versus',
            'bigger than', 'smaller than', 'faster than', 'slower than'
        ]
        
        self.superlative_words = [
            'most', 'least', 'best', 'worst', 'highest', 'lowest',
            'biggest', 'smallest', 'largest', 'tiniest', 'greatest',
            'leading', 'top', 'primary', 'main', 'chief'
        ]
        
        self.absolute_words = [
            'all', 'none', 'every', 'never', 'always', 'nobody',
            'everybody', 'anyone', 'no one', 'nothing', 'everything',
            'only', 'unique', 'sole', 'exclusive'
        ]
    
    def extract_claims(self, transcript: str) -> List[Dict]:
        """Extract potential factual claims from transcript"""
        claims = []
        
        # Split into sentences
        sentences = self._split_sentences(transcript)
        
        for idx, sentence in enumerate(sentences):
            # Skip very short sentences
            if len(sentence.split()) < 5:
                continue
            
            # Calculate claim score
            score, indicators = self._score_sentence(sentence)
            
            if score > 0:
                # Get surrounding context (previous and next sentence)
                context_parts = []
                if idx > 0:
                    context_parts.append(sentences[idx-1])
                context_parts.append(sentence)
                if idx < len(sentences) - 1:
                    context_parts.append(sentences[idx+1])
                
                full_context = ' '.join(context_parts)
                
                claim = {
                    'text': sentence.strip(),
                    'full_context': full_context.strip(),
                    'score': score,
                    'indicators': indicators,
                    'position': idx,
                    'word_count': len(sentence.split())
                }
                claims.append(claim)
        
        logger.info(f"Extracted {len(claims)} potential claims from {len(sentences)} sentences")
        return claims
    
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
    
    def prioritize_claims(self, claims: List[Dict]) -> List[Dict]:
        """Prioritize claims by importance and verifiability"""
        # Calculate priority score for each claim
        for claim in claims:
            priority = claim['score']
            
            # Boost priority for statistical claims
            if 'statistical' in claim['indicators']:
                priority += 2
            
            # Boost priority for cited sources
            if 'citation' in claim['indicators']:
                priority += 1
            
            # Boost priority for comparisons and superlatives
            if 'comparison' in claim['indicators'] or 'superlative' in claim['indicators']:
                priority += 1
            
            # Reduce priority for very long claims
            if claim['word_count'] > 50:
                priority -= 1
            
            claim['priority'] = priority
        
        # Sort by priority
        sorted_claims = sorted(claims, key=lambda x: x['priority'], reverse=True)
        
        # Return full claim objects (not just text)
        return sorted_claims
    
    def identify_speakers(self, transcript: str) -> Dict[str, int]:
        """Identify and count speaker mentions in transcript"""
        from collections import Counter
        
        speakers = []
        speaker_lines = {}  # Track what each speaker says
        
        # Common speaker patterns
        patterns = [
            # "SPEAKER NAME:" format
            r'^([A-Z][A-Z\s\.]+):',
            # "Speaker Name:" format  
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):',
            # Interview format "Q:" and "A:"
            r'^(Q|A|QUESTION|ANSWER|INTERVIEWER|INTERVIEWEE):'
        ]
        
        # Name patterns for mentions within text
        name_patterns = [
            # Titles + Names
            r'\b(President|Senator|Representative|Governor|Mayor|Dr\.|Mr\.|Mrs\.|Ms\.|Judge|Secretary)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # Full names (First Last)
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|IV))?)\b',
            # Last names after verbs
            r'(?:said|says?|stated|claimed|announced|declared|according to)\s+([A-Z][a-z]+)'
        ]
        
        lines = transcript.split('\n')
        current_speaker = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for speaker labels
            speaker_found = False
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    speaker = match.group(1).strip()
                    # Normalize Q&A format
                    if speaker in ['Q', 'QUESTION', 'INTERVIEWER']:
                        speaker = 'INTERVIEWER'
                    elif speaker in ['A', 'ANSWER', 'INTERVIEWEE']:
                        speaker = 'INTERVIEWEE'
                    
                    current_speaker = speaker
                    speakers.append(speaker)
                    
                    # Track what they say
                    content = line[match.end():].strip()
                    if speaker not in speaker_lines:
                        speaker_lines[speaker] = []
                    speaker_lines[speaker].append(content)
                    
                    speaker_found = True
                    break
            
            # If no speaker label, attribute to current speaker
            if not speaker_found and current_speaker:
                if current_speaker in speaker_lines:
                    speaker_lines[current_speaker].append(line)
            
            # Also look for name mentions in the content
            for pattern in name_patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        # Handle title + name pattern
                        if len(match) == 2 and match[0] in ['President', 'Senator', 'Representative', 'Governor', 'Mayor', 'Secretary', 'Judge']:
                            name = f"{match[0]} {match[1]}"
                        else:
                            name = match[1] if len(match) > 1 else match[0]
                    else:
                        name = match
                    
                    # Filter out common false positives
                    if name and len(name.split()) >= 2 and not any(word in name.lower() for word in ['the', 'and', 'or', 'but']):
                        speakers.append(name)
        
        # Count speaker occurrences
        speaker_counts = Counter(speakers)
        
        # Analyze who speaks the most
        word_counts = {}
        for speaker, lines in speaker_lines.items():
            total_words = sum(len(line.split()) for line in lines)
            word_counts[speaker] = total_words
        
        return {
            'speaker_mentions': dict(speaker_counts),
            'speaker_word_counts': word_counts,
            'main_speaker': max(word_counts.items(), key=lambda x: x[1])[0] if word_counts else None,
            'all_speakers': list(set(speakers))
        }
    
    def extract_key_topics(self, transcript: str) -> List[str]:
        """Extract main topics discussed in the transcript"""
        # Common topic indicators
        topic_patterns = [
            r'(?:about|regarding|concerning|on the topic of|discussing)\s+([A-Za-z\s]+)',
            r'(?:issue of|matter of|question of|problem of)\s+([A-Za-z\s]+)',
            r'(?:the|this)\s+([A-Za-z]+)\s+(?:crisis|situation|problem|issue|matter)'
        ]
        
        topics = []
        
        # Also look for frequently mentioned noun phrases
        words = transcript.lower().split()
        # Count 2-3 word phrases
        phrases = []
        for i in range(len(words) - 2):
            two_word = f"{words[i]} {words[i+1]}"
            three_word = f"{words[i]} {words[i+1]} {words[i+2]}"
            
            # Filter out phrases with common words
            if not any(common in two_word for common in ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']):
                phrases.append(two_word)
            if not any(common in three_word for common in ['the', 'and', 'or', 'but']):
                phrases.append(three_word)
        
        # Count phrase frequency
        phrase_counts = Counter(phrases)
        
        # Get top topics
        top_phrases = [phrase for phrase, count in phrase_counts.most_common(10) if count > 2]
        
        return top_phrases
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Basic sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Clean up sentences
        cleaned = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:
                cleaned.append(sentence)
        
        return cleaned
    
    def _score_sentence(self, sentence: str) -> tuple:
        """Score sentence for claim likelihood"""
        score = 0
        indicators = []
        
        sentence_lower = sentence.lower()
        
        # Check for statistical patterns
        for pattern in self.statistical_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                score += 2
                indicators.append('statistical')
                break
        
        # Check for factual indicators
        for indicator in self.factual_indicators:
            if indicator in sentence_lower:
                score += 2
                indicators.append('citation')
                break
        
        # Check for temporal indicators
        for indicator in self.temporal_indicators:
            if indicator in sentence_lower or re.search(indicator, sentence):
                score += 1
                indicators.append('temporal')
                break
        
        # Check for comparisons
        for comparison in self.comparison_words:
            if comparison in sentence_lower:
                score += 1
                indicators.append('comparison')
                break
        
        # Check for superlatives
        for superlative in self.superlative_words:
            if superlative in sentence_lower:
                score += 1
                indicators.append('superlative')
                break
        
        # Check for absolute statements
        for absolute in self.absolute_words:
            if f' {absolute} ' in f' {sentence_lower} ':
                score += 1
                indicators.append('absolute')
                break
        
        # Check for specific entities (capitalized words)
        capital_words = re.findall(r'\b[A-Z][a-z]+\b', sentence)
        if len(capital_words) >= 2:
            score += 1
            indicators.append('entities')
        
        return score, indicators
    
    def _is_opinion(self, text: str) -> bool:
        """Check if text is likely an opinion"""
        opinion_indicators = [
            'i think', 'i believe', 'in my opinion', 'i feel',
            'it seems', 'probably', 'maybe', 'perhaps', 'might',
            'could be', 'should', 'ought to', 'better to'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in opinion_indicators)
    
    def _is_prediction(self, text: str) -> bool:
        """Check if text is a prediction about the future"""
        future_indicators = [
            'will be', 'going to', 'expected to', 'predicted to',
            'forecast', 'projection', 'by 2025', 'by 2030',
            'in the future', 'next year', 'coming years'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in future_indicators)
    
    def _is_too_vague(self, text: str) -> bool:
        """Check if claim is too vague to verify"""
        vague_indicators = [
            'some people', 'many people', 'a lot of', 'several',
            'various', 'numerous', 'multiple', 'certain',
            'somewhere', 'somehow', 'something', 'someone'
        ]
        
        text_lower = text.lower()
        vague_count = sum(1 for indicator in vague_indicators if indicator in text_lower)
        
        # Too vague if multiple vague indicators
        return vague_count >= 2
