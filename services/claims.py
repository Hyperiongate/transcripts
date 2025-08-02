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
                claim = {
                    'text': sentence.strip(),
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
    
    def prioritize_claims(self, claims: List[Dict]) -> List[str]:
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
        
        # Return just the claim text strings for fact checking
        return [claim['text'] for claim in sorted_claims]
    
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
