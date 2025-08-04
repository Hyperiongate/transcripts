"""
Verdict Definitions and Mapping Module
Defines verdict types and handles verdict mapping from various sources
"""

class VerdictDefinitions:
    """Define and manage fact-checking verdicts"""
    
    # Enhanced verdict definitions with clearer language
    VERDICTS = {
        'true': {
            'label': 'True',
            'icon': '✓',
            'description': 'The claim is accurate and supported by evidence',
            'weight': 1.0
        },
        'mostly_true': {
            'label': 'Mostly True',
            'icon': '◐',
            'description': 'The claim is largely accurate with minor caveats',
            'weight': 0.75
        },
        'mixed': {
            'label': 'Mixed',
            'icon': '◓',
            'description': 'The claim contains both true and false elements',
            'weight': 0.5
        },
        'deceptive': {  # Renamed from 'misleading'
            'label': 'Deceptive',
            'icon': '⚠️',
            'description': 'The claim uses true facts in a deliberately deceptive way',
            'weight': 0.3
        },
        'lacks_context': {
            'label': 'Lacks Critical Context',
            'icon': '🔍',
            'description': 'The claim omits crucial information that changes its meaning',
            'weight': 0.4
        },
        'unsubstantiated': {
            'label': 'Unsubstantiated',
            'icon': '❓',
            'description': 'The claim lacks evidence and has been repeated without proof',
            'weight': 0.2
        },
        'mostly_false': {
            'label': 'Mostly False',
            'icon': '◑',
            'description': 'The claim is largely inaccurate with a grain of truth',
            'weight': 0.25
        },
        'false': {
            'label': 'False',
            'icon': '✗',
            'description': 'The claim is demonstrably false',
            'weight': 0.0
        },
        'unverified': {
            'label': 'Unverified',
            'icon': '?',
            'description': 'Insufficient evidence to determine truth',
            'weight': None
        }
    }
    
    @classmethod
    def get_verdict_info(cls, verdict: str) -> dict:
        """Get information about a verdict"""
        # Handle old 'misleading' verdicts
        if verdict == 'misleading':
            verdict = 'deceptive'
        return cls.VERDICTS.get(verdict, cls.VERDICTS['unverified'])
    
    @classmethod
    def map_google_rating(cls, rating: str) -> str:
        """Map Google Fact Check ratings to our verdict system"""
        rating_lower = rating.lower()
        
        # Direct mappings
        mappings = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'half true': 'mixed',
            'mostly false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'misleading': 'deceptive',  # Changed
            'lacks context': 'lacks_context',
            'missing context': 'lacks_context',
            'unsubstantiated': 'unsubstantiated',
            'unproven': 'unsubstantiated',
            'mixture': 'mixed',
            'outdated': 'mostly_false',
            'scam': 'false',
            'legend': 'false',
            'fiction': 'false',
            'satire': 'false',
            'deceptive': 'deceptive'
        }
        
        # Check each mapping
        for key, verdict in mappings.items():
            if key in rating_lower:
                # Special handling for qualified ratings
                if 'not' in rating_lower and verdict in ['true', 'mostly_true']:
                    return 'false'
                return verdict
        
        # Pattern-based mappings
        if 'true' in rating_lower and 'not' not in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_true'
            return 'true'
        
        if 'false' in rating_lower:
            if 'mostly' in rating_lower or 'partly' in rating_lower:
                return 'mostly_false'
            return 'false'
        
        # Default
        return 'unverified'
    
    @classmethod
    def extract_verdict_from_text(cls, text: str) -> str:
        """Extract verdict from AI analysis or other text"""
        text_lower = text.lower()
        
        # Check for explicit verdict mentions (in order of specificity)
        verdict_keywords = [
            ('deceptive', 'deceptive'),
            ('deliberately misleading', 'deceptive'),
            ('intentionally misleading', 'deceptive'),
            ('misleading', 'deceptive'),
            ('lacks context', 'lacks_context'),
            ('missing context', 'lacks_context'),
            ('unsubstantiated', 'unsubstantiated'),
            ('no evidence', 'unsubstantiated'),
            ('mostly true', 'mostly_true'),
            ('largely true', 'mostly_true'),
            ('mostly accurate', 'mostly_true'),
            ('mostly false', 'mostly_false'),
            ('largely false', 'mostly_false'),
            ('mixed', 'mixed'),
            ('partially true', 'mixed'),
            ('partially false', 'mixed'),
            ('true', 'true'),
            ('accurate', 'true'),
            ('correct', 'true'),
            ('confirmed', 'true'),
            ('false', 'false'),
            ('incorrect', 'false'),
            ('wrong', 'false'),
            ('debunked', 'false'),
            ('refuted', 'false')
        ]
        
        for keyword, verdict in verdict_keywords:
            if keyword in text_lower:
                # Check for negation
                words_before = text_lower.split(keyword)[0].split()[-3:]
                if any(neg in words_before for neg in ['not', 'no', "isn't", "aren't", "wasn't"]):
                    # Flip the verdict
                    if verdict in ['true', 'mostly_true']:
                        return 'false'
                    elif verdict in ['false', 'mostly_false']:
                        return 'true'
                return verdict
        
        # Sentiment-based fallback
        positive_indicators = ['accurate', 'correct', 'verified', 'confirms', 'supports', 'validated']
        negative_indicators = ['incorrect', 'wrong', 'debunked', 'refuted', 'contradicts', 'disproven']
        
        positive_count = sum(1 for word in positive_indicators if word in text_lower)
        negative_count = sum(1 for word in negative_indicators if word in text_lower)
        
        if positive_count > negative_count:
            return 'mostly_true'
        elif negative_count > positive_count:
            return 'mostly_false'
        else:
            return 'mixed'
    
    @classmethod
    def calculate_credibility_score(cls, verdicts: list) -> int:
        """Calculate overall credibility score from verdict list"""
        if not verdicts:
            return 0
        
        total_weight = 0
        weighted_sum = 0
        
        for verdict in verdicts:
            # Handle old 'misleading' verdicts
            if verdict == 'misleading':
                verdict = 'deceptive'
            
            verdict_info = cls.get_verdict_info(verdict)
            weight = verdict_info.get('weight')
            
            if weight is not None:
                total_weight += 1
                weighted_sum += weight
        
        if total_weight == 0:
            return 50  # Default neutral score
        
        return int((weighted_sum / total_weight) * 100)
    
    @classmethod
    def get_deception_analysis(cls, verdicts: list) -> dict:
        """Analyze patterns of deception"""
        deceptive_count = sum(1 for v in verdicts if v in ['deceptive', 'misleading'])
        lacks_context_count = sum(1 for v in verdicts if v == 'lacks_context')
        false_count = sum(1 for v in verdicts if v in ['false', 'mostly_false'])
        
        analysis = {
            'deceptive_statements': deceptive_count,
            'context_omissions': lacks_context_count,
            'false_statements': false_count,
            'deception_pattern': None
        }
        
        # Identify patterns
        total_problematic = deceptive_count + lacks_context_count + false_count
        
        if total_problematic == 0:
            analysis['deception_pattern'] = 'No deception detected'
        elif deceptive_count >= 3:
            analysis['deception_pattern'] = 'Pattern of deliberate deception'
        elif lacks_context_count >= 3:
            analysis['deception_pattern'] = 'Pattern of strategic omission'
        elif false_count >= 3:
            analysis['deception_pattern'] = 'Pattern of false statements'
        elif total_problematic >= 5:
            analysis['deception_pattern'] = 'Mixed pattern of deception'
        
        return analysis
