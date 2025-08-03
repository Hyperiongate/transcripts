"""
Context Resolution Module
Handles pronoun resolution and contextual understanding
"""
import re
from typing import List, Tuple, Dict, Optional

class ContextResolver:
    """Resolve contextual references in claims"""
    
    def __init__(self):
        self.previous_claims = []
        self.max_context_size = 10
        
    def add_claim_to_context(self, claim: str):
        """Add a claim to the context history"""
        self.previous_claims.append(claim)
        if len(self.previous_claims) > self.max_context_size:
            self.previous_claims.pop(0)
    
    def resolve_context(self, claim: str) -> Tuple[str, Dict]:
        """Understand and resolve contextual references in claims"""
        original_claim = claim
        context_info = {'original': original_claim, 'resolved': False}
        
        # Resolve pronouns
        if any(pronoun in claim.lower().split() for pronoun in ['they', 'it', 'this', 'that']):
            resolved_claim = self._resolve_pronouns(claim)
            if resolved_claim != claim:
                claim = resolved_claim
                context_info['resolved'] = True
                context_info['resolved_claim'] = claim
        
        # Handle contextual understanding
        claim = self._apply_contextual_knowledge(claim, context_info)
        
        return claim, context_info
    
    def _resolve_pronouns(self, claim: str) -> str:
        """Resolve pronoun references"""
        claim_lower = claim.lower()
        
        # Resolve "they"
        if 'they' in claim_lower:
            claim = self._resolve_they_reference(claim)
        
        # Resolve "it"
        if ' it ' in claim_lower or claim_lower.startswith('it '):
            claim = self._resolve_it_reference(claim)
        
        # Resolve "this/that"
        if 'this' in claim_lower or 'that' in claim_lower:
            claim = self._resolve_this_that_reference(claim)
        
        return claim
    
    def _resolve_they_reference(self, claim: str) -> str:
        """Resolve 'they' references from context"""
        for prev_claim in reversed(self.previous_claims[-3:]):
            # Find organization names
            orgs = re.findall(
                r'\b(?:Democrats?|Republicans?|Congress|Senate|House|'
                r'Administration|Government|Company|Corporation|'
                r'[A-Z][a-z]+\s+(?:Inc|Corp|LLC|Ltd))\b', 
                prev_claim, re.I
            )
            if orgs:
                return re.sub(r'\bthey\b', orgs[0], claim, flags=re.I)
            
            # Find people references
            people = re.findall(
                r'\b(?:Mr\.|Ms\.|Dr\.|President|Senator|Representative|'
                r'Governor|Mayor|CEO|Director)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', 
                prev_claim
            )
            if people:
                return re.sub(r'\bthey\b', people[0], claim, flags=re.I)
        
        return claim
    
    def _resolve_it_reference(self, claim: str) -> str:
        """Resolve 'it' references from context"""
        for prev_claim in reversed(self.previous_claims[-2:]):
            # Look for policies, bills, or things
            things = re.findall(
                r'(?:the|a)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
                r'(?:Act|Bill|Policy|Plan|Program|Law|Regulation|Treaty|Agreement))', 
                prev_claim
            )
            if things:
                return re.sub(r'\bit\b', things[0], claim, flags=re.I)
            
            # Look for concepts or ideas
            concepts = re.findall(
                r'(?:the|this|that)\s+([a-z]+(?:\s+[a-z]+)*)\s+(?:is|was|will|would|could|should)', 
                prev_claim.lower()
            )
            if concepts and len(concepts[0]) > 3:
                return claim.replace(' it ', f' {concepts[0]} ')
        
        return claim
    
    def _resolve_this_that_reference(self, claim: str) -> str:
        """Resolve 'this/that' references from context"""
        if not self.previous_claims:
            return claim
        
        prev = self.previous_claims[-1]
        
        # Extract the main subject from previous claim
        subjects = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', prev)
        if subjects:
            # Replace 'this' or 'that' with the most prominent subject
            main_subject = max(subjects, key=len)
            claim = re.sub(r'\bthis\b', main_subject, claim, count=1, flags=re.I)
            claim = re.sub(r'\bthat\b', main_subject, claim, count=1, flags=re.I)
        
        return claim
    
    def _apply_contextual_knowledge(self, claim: str, context_info: Dict) -> str:
        """Apply domain-specific contextual understanding"""
        claim_lower = claim.lower()
        
        # Sports context
        golf_terms = ['putting', 'golf', 'pga', 'masters', 'tournament', 'birdie', 'eagle', 'par']
        if 'tiger' in claim_lower and any(term in claim_lower for term in golf_terms):
            claim = re.sub(r'\btiger\b', 'Tiger Woods', claim, flags=re.I)
            context_info['inferred_subject'] = 'Tiger Woods (golfer)'
        
        # Political context
        if 'the president' in claim_lower and not any(name in claim for name in ['Biden', 'Trump', 'Obama']):
            # Could add current president based on date
            context_info['needs_clarification'] = 'Which president?'
        
        # Economic context
        if 'the fed' in claim_lower:
            claim = claim.replace('the fed', 'the Federal Reserve')
            claim = claim.replace('The Fed', 'The Federal Reserve')
            context_info['expanded'] = 'Federal Reserve'
        
        # Tech context
        tech_abbreviations = {
            'ai': 'artificial intelligence',
            'ml': 'machine learning',
            'api': 'application programming interface',
            'ui': 'user interface',
            'ux': 'user experience'
        }
        
        for abbrev, full in tech_abbreviations.items():
            if f' {abbrev} ' in claim_lower:
                claim = re.sub(f'\\b{abbrev}\\b', full, claim, flags=re.I)
                context_info['expanded'] = full
        
        return claim
    
    def check_vagueness(self, claim: str) -> Dict:
        """Check if a claim is too vague to verify"""
        claim_lower = claim.lower()
        
        # Vague pronouns without clear antecedents
        if claim_lower.startswith(('they ', 'it ', 'this ', 'that ')) and len(self.previous_claims) == 0:
            return {'is_vague': True, 'reason': 'Unclear pronoun reference without context'}
        
        # Too short
        if len(claim.split()) < 5:
            return {'is_vague': True, 'reason': 'Claim too brief to verify'}
        
        # No specific claims
        vague_phrases = [
            'some people say', 'everyone knows', 'it is said', 
            'many believe', 'they say', 'people think', 'sources say',
            'experts believe', 'studies show', 'research indicates'
        ]
        
        for phrase in vague_phrases:
            if phrase in claim_lower and not any(
                specific in claim for specific in ['%', 'percent', 'million', 'billion', '$']
            ):
                return {'is_vague': True, 'reason': f'Vague attribution: "{phrase}"'}
        
        # Pure opinion
        opinion_words = ['beautiful', 'amazing', 'terrible', 'wonderful', 'horrible', 'best', 'worst']
        if any(word in claim_lower for word in opinion_words) and not any(char.isdigit() for char in claim):
            return {'is_vague': True, 'reason': 'Subjective opinion rather than factual claim'}
        
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
