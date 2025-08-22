"""
Enhanced Context Resolution Service - Less Restrictive
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

class ContextResolver:
    """Resolve contextual references in claims - LESS RESTRICTIVE VERSION"""
    
    def __init__(self):
        self.entities = defaultdict(list)
        self.previous_claims = []
        self.name_map = {}
        self.max_context_size = 10
    
    def analyze_full_transcript(self, transcript: str):
        """Extract entities from full transcript"""
        # Extract names (proper nouns)
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        names = re.findall(name_pattern, transcript)
        
        for name in names:
            if len(name.split()) <= 3:  # Reasonable name length
                self.entities['people'].append(name)
        
        # Extract organizations
        org_indicators = ['Company', 'Corporation', 'Inc', 'LLC', 'Organization', 'Department', 'Agency']
        for indicator in org_indicators:
            pattern = rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+{indicator})'
            orgs = re.findall(pattern, transcript)
            self.entities['organizations'].extend(orgs)
        
        # Extract locations
        location_pattern = r'\b(?:in|at|from|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        locations = re.findall(location_pattern, transcript)
        self.entities['locations'].extend(locations)
        
        # Extract topics
        self._extract_topics(transcript)
    
    def _extract_topics(self, transcript: str):
        """Extract main topics from transcript"""
        topic_keywords = {
            'economy': ['economy', 'economic', 'gdp', 'growth', 'recession', 'inflation', 'jobs'],
            'healthcare': ['healthcare', 'health', 'medical', 'insurance', 'medicare', 'medicaid', 'obamacare'],
            'education': ['education', 'schools', 'students', 'teachers', 'college', 'university'],
            'climate': ['climate', 'warming', 'carbon', 'emissions', 'renewable', 'energy', 'environment'],
            'security': ['security', 'defense', 'military', 'terrorism', 'safety', 'protection', 'police'],
            'immigration': ['immigration', 'immigrant', 'border', 'citizenship', 'refugee', 'asylum'],
            'taxes': ['tax', 'taxes', 'irs', 'deduction', 'revenue', 'fiscal'],
            'crime': ['crime', 'criminal', 'prison', 'jail', 'police', 'law enforcement', 'justice'],
            'infrastructure': ['infrastructure', 'roads', 'bridges', 'transportation', 'transit', 'highway']
        }
        
        transcript_lower = transcript.lower()
        self.entities['topics'] = []
        
        for topic, keywords in topic_keywords.items():
            count = sum(1 for keyword in keywords if keyword in transcript_lower)
            if count >= 2:  # Topic mentioned at least twice
                self.entities['topics'].append(topic)
    
    def add_claim_to_context(self, claim: str):
        """Add a claim to the context history"""
        self.previous_claims.append(claim)
        if len(self.previous_claims) > self.max_context_size:
            self.previous_claims.pop(0)
    
    def resolve_context(self, claim: str) -> Tuple[str, Dict]:
        """Resolve contextual references in claims"""
        original_claim = claim
        context_info = {'original': original_claim, 'resolved': False, 'resolutions': []}
        
        # Resolve partial names first
        claim = self._resolve_partial_names(claim, context_info)
        
        # Resolve pronouns
        if any(pronoun in claim.lower().split() for pronoun in ['they', 'it', 'this', 'that', 'he', 'she', 'his', 'her', 'their']):
            resolved_claim = self._resolve_pronouns(claim)
            if resolved_claim != claim:
                claim = resolved_claim
                context_info['resolved'] = True
                context_info['resolved_claim'] = claim
        
        # Handle contextual understanding
        claim = self._apply_contextual_knowledge(claim, context_info)
        
        # Add to context for future claims
        self.add_claim_to_context(original_claim)
        
        return claim, context_info
    
    def _resolve_partial_names(self, claim: str, context_info: Dict) -> str:
        """Resolve partial name references"""
        # Map of common partial references
        name_mappings = {
            'Trump': 'Donald Trump',
            'Biden': 'Joe Biden',
            'Harris': 'Kamala Harris',
            'Obama': 'Barack Obama',
            'Clinton': 'Hillary Clinton',
            'Bush': 'George W. Bush',
            'Vance': 'J.D. Vance'
        }
        
        for partial, full in name_mappings.items():
            if partial in claim and full not in claim:
                claim = claim.replace(partial, full)
                context_info['resolutions'].append(f"Resolved '{partial}' to '{full}'")
        
        return claim
    
    def _resolve_pronouns(self, claim: str) -> str:
        """Resolve pronoun references"""
        # Look for the most recent entity mentioned
        if self.previous_claims:
            # Simple heuristic: use the last mentioned person
            for prev_claim in reversed(self.previous_claims):
                # Find proper nouns in previous claims
                names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', prev_claim)
                if names:
                    # Replace pronouns with the last mentioned name
                    claim = re.sub(r'\b(he|she|they)\b', names[0], claim, flags=re.IGNORECASE)
                    claim = re.sub(r'\b(his|her|their)\b', f"{names[0]}'s", claim, flags=re.IGNORECASE)
                    break
        
        return claim
    
    def _apply_contextual_knowledge(self, claim: str, context_info: Dict) -> str:
        """Apply contextual knowledge to clarify claims"""
        # Add context to vague references
        replacements = {
            'the president': 'President Trump',  # Current as of 2025
            'the administration': 'the Trump administration',
            'the former president': 'former President Biden',
            'the vice president': 'Vice President Vance',
            'the election': 'the 2024 election',
            'last year': 'in 2024',
            'this year': 'in 2025'
        }
        
        claim_lower = claim.lower()
        for vague, specific in replacements.items():
            if vague in claim_lower:
                claim = re.sub(vague, specific, claim, flags=re.IGNORECASE)
                context_info['resolutions'].append(f"Clarified '{vague}' to '{specific}'")
        
        return claim
    
    def is_claim_too_vague(self, claim: str) -> Dict:
        """Check if a claim is too vague to verify - LESS RESTRICTIVE"""
        claim_lower = claim.lower()
        
        # Only mark as vague if REALLY vague
        if len(claim.split()) < 3:  # Very short
            return {'is_vague': True, 'reason': 'Claim too brief to verify'}
        
        # Check for claims that are just pronouns
        if claim_lower.strip() in ['they', 'it', 'this', 'that', 'those', 'these']:
            return {'is_vague': True, 'reason': 'Claim is just a pronoun'}
        
        # Check for completely unspecific claims
        ultra_vague = ['something', 'someone said', 'they said', 'it happened']
        for phrase in ultra_vague:
            if phrase == claim_lower.strip():
                return {'is_vague': True, 'reason': 'Claim has no specific content'}
        
        # Otherwise, assume it can be checked
        return {'is_vague': False}
    
    def extract_claim_source(self, claim: str) -> Optional[str]:
        """Extract who is making the claim"""
        patterns = [
            # "According to X"
            r'(?:According to|Says?|Claims?|States?|Reported by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # "X said/claims"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|says|claimed|claims|stated|states|reported|reports)',
            # "X: [claim]"
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):',
            # Quoted sources
            r'"[^"]+"\s*[-—]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # News organizations
            r'\b(CNN|Fox News|MSNBC|Reuters|AP|BBC|NPR|The New York Times|The Washington Post)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, claim, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def get_context_summary(self) -> Dict:
        """Get a summary of the extracted context"""
        return {
            'people': len(self.entities.get('people', [])),
            'organizations': len(self.entities.get('organizations', [])),
            'locations': len(self.entities.get('locations', [])),
            'events': len(self.entities.get('events', [])),
            'topics': self.entities.get('topics', []),
            'name_mappings': len(self.name_map),
            'total_entities': sum(len(v) for v in self.entities.values())
        }
