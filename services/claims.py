"""
Enhanced Claim Extraction Service
Handles attribution and focuses on the actual claims being made
"""
import re
import logging
from typing import List, Dict, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

class ClaimExtractor:
    """Extract and analyze factual claims from text"""
    
    def __init__(self):
        # Attribution patterns to detect
        self.attribution_patterns = [
            r'(?:I|we|he|she|they)\s+(?:said|told|claimed|stated|mentioned|argued|suggested)\s+(?:that\s+)?',
            r'(?:according to|as I said|as we discussed|as mentioned)\s+(?:last week|yesterday|before|earlier|previously)',
            r'(?:I|we)\s+(?:previously|already|once)\s+(?:said|stated|mentioned|explained)',
            r'(?:remember when|recall that|don\'t forget)\s+(?:I|we|he|she|they)\s+(?:said|told)',
            r'(?:my|our|his|her|their)\s+(?:previous|earlier|prior)\s+(?:statement|claim|assertion)',
        ]
        
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
            
            # Extract the actual claim from attributed statements
            actual_claim, attribution_info = self._extract_actual_claim(sentence)
            
            # Calculate claim score
            score, indicators = self._score_sentence(actual_claim)
            
            if score > 0:
                claim = {
                    'text': actual_claim.strip(),
                    'original_text': sentence.strip(),
                    'score': score,
                    'indicators': indicators,
                    'position': idx,
                    'word_count': len(actual_claim.split()),
                    'has_attribution': attribution_info['has_attribution'],
                    'attribution_type': attribution_info['type'],
                    'attribution_context': attribution_info['context']
                }
                claims.append(claim)
        
        logger.info(f"Extracted {len(claims)} potential claims from {len(sentences)} sentences")
        return claims
    
    def _extract_actual_claim(self, sentence: str) -> Tuple[str, Dict]:
        """Extract the actual claim from a sentence, removing attribution"""
        attribution_info = {
            'has_attribution': False,
            'type': None,
            'context': None
        }
        
        # Check for attribution patterns
        for pattern in self.attribution_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                attribution_info['has_attribution'] = True
                attribution_info['context'] = match.group(0)
                
                # Determine attribution type
                if 'last week' in match.group(0).lower() or 'previously' in match.group(0).lower():
                    attribution_info['type'] = 'past_reference'
                elif 'I said' in match.group(0) or 'we said' in match.group(0):
                    attribution_info['type'] = 'self_reference'
                else:
                    attribution_info['type'] = 'other_reference'
                
                # Extract the actual claim after the attribution
                claim_start = match.end()
                actual_claim = sentence[claim_start:].strip()
                
                # Handle quoted claims
                quote_match = re.search(r'["\'](.+?)["\']', actual_claim)
                if quote_match:
                    actual_claim = quote_match.group(1)
                
                # If the claim is too short after extraction, use the full sentence
                if len(actual_claim.split()) < 3:
                    actual_claim = sentence
                
                return actual_claim, attribution_info
        
        # No attribution found, return original sentence
        return sentence, attribution_info
    
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
            
            # IMPORTANT: Boost priority for attributed claims (they often contain false info)
            if claim['has_attribution']:
                priority += 2  # These need extra scrutiny
                
            # Reduce priority for very long claims
            if claim['word_count'] > 50:
                priority -= 1
            
            claim['priority'] = priority
        
        # Sort by priority
        sorted_claims = sorted(claims, key=lambda x: x['priority'], reverse=True)
        
        # Return enriched claim data for fact checking
        return sorted_claims
    
    def prepare_claims_for_checking(self, claims: List[Dict]) -> List[Dict]:
        """Prepare claims with context for fact checking"""
        prepared_claims = []
        
        for claim in claims:
            prepared_claim = {
                'claim': claim['text'],
                'metadata': {
                    'has_attribution': claim['has_attribution'],
                    'attribution_type': claim['attribution_type'],
                    'original_text': claim['original_text'],
                    'indicators': claim['indicators'],
                    'priority': claim.get('priority', 0)
                }
            }
            
            # Add special instructions for attributed claims
            if claim['has_attribution']:
                if claim['attribution_type'] == 'past_reference':
                    prepared_claim['check_instruction'] = "Verify the factual accuracy of this claim, not when it was said"
                elif claim['attribution_type'] == 'self_reference':
                    prepared_claim['check_instruction'] = "Check if this claim is factually true, regardless of who said it"
            
            prepared_claims.append(prepared_claim)
        
        return prepared_claims
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Improved sentence splitting that handles quotes better
        # First, protect quoted content
        protected_text = text
        quotes = re.findall(r'"[^"]+?"', text)
        for i, quote in enumerate(quotes):
            protected_text = protected_text.replace(quote, f"__QUOTE_{i}__")
        
        # Split sentences
        sentences = re.split(r'(?<=[.!?])\s+', protected_text)
        
        # Restore quotes
        restored_sentences = []
        for sentence in sentences:
            for i, quote in enumerate(quotes):
                sentence = sentence.replace(f"__QUOTE_{i}__", quote)
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:
                restored_sentences.append(sentence)
        
        return restored_sentences
    
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
