"""
Fact Check History Tracking Module
Tracks historical claims and patterns for better context
"""
import re
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

class FactCheckHistory:
    """Track historical claims and patterns"""
    
    def __init__(self):
        self.claim_history = defaultdict(list)  # claim_hash -> list of checks
        self.source_patterns = defaultdict(lambda: defaultdict(int))  # source -> verdict -> count
        self.misleading_patterns = defaultdict(list)  # source -> list of misleading claims
        
    def add_check(self, claim: str, source: str, verdict: str, explanation: str):
        """Add a fact check to history"""
        claim_hash = self._hash_claim(claim)
        check_data = {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'verdict': verdict,
            'explanation': explanation
        }
        self.claim_history[claim_hash].append(check_data)
        self.source_patterns[source][verdict] += 1
        
        if verdict in ['misleading', 'mostly_false', 'false']:
            self.misleading_patterns[source].append({
                'claim': claim,
                'verdict': verdict,
                'timestamp': datetime.now().isoformat()
            })
    
    def get_historical_context(self, claim: str, source: str) -> Optional[Dict]:
        """Get historical context for a claim"""
        claim_hash = self._hash_claim(claim)
        
        # Check if this exact claim has been checked before
        if claim_hash in self.claim_history:
            past_checks = self.claim_history[claim_hash]
            return {
                'previously_checked': True,
                'check_count': len(past_checks),
                'past_verdicts': [c['verdict'] for c in past_checks],
                'first_checked': past_checks[0]['timestamp']
            }
        
        # Check source's pattern of false claims
        source_stats = self.source_patterns.get(source, {})
        if source_stats:
            total_claims = sum(source_stats.values())
            false_claims = source_stats.get('false', 0) + source_stats.get('mostly_false', 0)
            misleading_claims = source_stats.get('misleading', 0)
            
            return {
                'source_history': {
                    'total_claims': total_claims,
                    'false_claims': false_claims,
                    'misleading_claims': misleading_claims,
                    'reliability_score': 1 - (false_claims + misleading_claims * 0.5) / total_claims if total_claims > 0 else None
                }
            }
        
        return None
    
    def _hash_claim(self, claim: str) -> str:
        """Create a normalized hash for claim comparison"""
        # Normalize the claim for comparison
        normalized = re.sub(r'\s+', ' ', claim.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Simple hash - in production, use proper hashing
        return str(hash(normalized))
    
    def get_repeat_offenders(self, threshold: int = 3) -> List[Dict]:
        """Get sources that have made multiple false claims"""
        offenders = []
        
        for source, verdicts in self.source_patterns.items():
            false_count = verdicts.get('false', 0) + verdicts.get('mostly_false', 0)
            misleading_count = verdicts.get('misleading', 0)
            
            if false_count >= threshold or (false_count + misleading_count) >= threshold * 1.5:
                total_claims = sum(verdicts.values())
                offenders.append({
                    'source': source,
                    'total_claims': total_claims,
                    'false_claims': false_count,
                    'misleading_claims': misleading_count,
                    'false_rate': false_count / total_claims if total_claims > 0 else 0
                })
        
        return sorted(offenders, key=lambda x: x['false_rate'], reverse=True)
