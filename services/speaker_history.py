"""
Speaker History Tracking Module
Tracks historical patterns and credibility of speakers/sources
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class SpeakerHistoryTracker:
    """Track and analyze speaker credibility history"""
    
    def __init__(self, storage_path: str = "data/speaker_history.json"):
        self.storage_path = storage_path
        self.history = self._load_history()
        
    def _load_history(self) -> Dict:
        """Load history from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading speaker history: {e}")
        return {}
    
    def _save_history(self):
        """Save history to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving speaker history: {e}")
    
    def extract_speaker(self, source: str, transcript: str) -> Optional[str]:
        """Extract speaker identity from source and transcript"""
        # Simple extraction - could be enhanced with NLP
        source_lower = source.lower()
        
        # Known speakers/sources
        known_speakers = {
            'trump': 'Donald Trump',
            'biden': 'Joe Biden',
            'obama': 'Barack Obama',
            'harris': 'Kamala Harris',
            'desantis': 'Ron DeSantis',
            'sanders': 'Bernie Sanders',
            'aoc': 'Alexandria Ocasio-Cortez',
            'pelosi': 'Nancy Pelosi',
            'mcconnell': 'Mitch McConnell'
        }
        
        for key, name in known_speakers.items():
            if key in source_lower:
                return name
        
        # Try to extract from source title
        if 'speech by' in source_lower:
            return source_lower.split('speech by')[1].strip().title()
        elif 'interview with' in source_lower:
            return source_lower.split('interview with')[1].strip().title()
        
        return None
    
    def add_analysis(self, speaker: str, analysis_results: Dict):
        """Add a new analysis to speaker history"""
        if not speaker:
            return
        
        if speaker not in self.history:
            self.history[speaker] = {
                'first_analyzed': datetime.now().isoformat(),
                'analyses': [],
                'total_claims': 0,
                'false_claims': 0,
                'misleading_claims': 0,
                'true_claims': 0,
                'patterns': []
            }
        
        # Extract key metrics
        false_count = sum(1 for fc in analysis_results['fact_checks'] 
                         if fc.get('verdict') in ['false', 'mostly_false'])
        misleading_count = sum(1 for fc in analysis_results['fact_checks'] 
                              if fc.get('verdict') == 'misleading')
        true_count = sum(1 for fc in analysis_results['fact_checks'] 
                        if fc.get('verdict') in ['true', 'mostly_true'])
        
        # Add to history
        analysis_summary = {
            'date': datetime.now().isoformat(),
            'source': analysis_results.get('source', 'Unknown'),
            'credibility_score': analysis_results['credibility_score'],
            'total_claims': analysis_results['checked_claims'],
            'false_claims': false_count,
            'misleading_claims': misleading_count,
            'true_claims': true_count
        }
        
        self.history[speaker]['analyses'].append(analysis_summary)
        self.history[speaker]['total_claims'] += analysis_results['checked_claims']
        self.history[speaker]['false_claims'] += false_count
        self.history[speaker]['misleading_claims'] += misleading_count
        self.history[speaker]['true_claims'] += true_count
        
        # Update patterns
        self._update_patterns(speaker)
        
        # Save
        self._save_history()
    
    def _update_patterns(self, speaker: str):
        """Identify patterns in speaker's history"""
        data = self.history[speaker]
        patterns = []
        
        # Calculate rates
        total = data['total_claims']
        if total > 0:
            false_rate = data['false_claims'] / total
            misleading_rate = data['misleading_claims'] / total
            
            # Pattern identification
            if false_rate > 0.3:
                patterns.append(f"High rate of false claims ({false_rate:.1%})")
            
            if misleading_rate > 0.2:
                patterns.append(f"Frequent use of misleading statements ({misleading_rate:.1%})")
            
            if len(data['analyses']) >= 3:
                # Check for improvement or deterioration
                recent_scores = [a['credibility_score'] for a in data['analyses'][-3:]]
                older_scores = [a['credibility_score'] for a in data['analyses'][:-3]]
                
                if older_scores:
                    recent_avg = sum(recent_scores) / len(recent_scores)
                    older_avg = sum(older_scores) / len(older_scores)
                    
                    if recent_avg < older_avg - 10:
                        patterns.append("Declining credibility trend")
                    elif recent_avg > older_avg + 10:
                        patterns.append("Improving credibility trend")
            
            # Topic-specific patterns (would need more sophisticated analysis)
            if data['misleading_claims'] > 5:
                patterns.append("Pattern of contextual manipulation")
        
        data['patterns'] = patterns
    
    def get_speaker_summary(self, speaker: str) -> Optional[Dict]:
        """Get comprehensive summary for a speaker"""
        if speaker not in self.history:
            return None
        
        data = self.history[speaker]
        analyses = data['analyses']
        
        if not analyses:
            return None
        
        # Calculate aggregate metrics
        total_analyses = len(analyses)
        avg_credibility = sum(a['credibility_score'] for a in analyses) / total_analyses
        
        # Recent performance (last 3 analyses)
        recent_analyses = analyses[-3:] if len(analyses) >= 3 else analyses
        recent_avg = sum(a['credibility_score'] for a in recent_analyses) / len(recent_analyses)
        
        return {
            'speaker': speaker,
            'total_analyses': total_analyses,
            'first_analyzed': data['first_analyzed'],
            'average_credibility': avg_credibility,
            'recent_credibility': recent_avg,
            'total_claims': data['total_claims'],
            'total_false_claims': data['false_claims'],
            'total_misleading_claims': data['misleading_claims'],
            'false_claim_rate': data['false_claims'] / data['total_claims'] if data['total_claims'] > 0 else 0,
            'patterns': data['patterns'],
            'previous_analyses': analyses
        }
    
    def get_comparative_analysis(self, speakers: List[str]) -> Dict:
        """Compare multiple speakers"""
        comparison = {}
        
        for speaker in speakers:
            if speaker in self.history:
                summary = self.get_speaker_summary(speaker)
                if summary:
                    comparison[speaker] = {
                        'average_credibility': summary['average_credibility'],
                        'false_claim_rate': summary['false_claim_rate'],
                        'total_analyses': summary['total_analyses']
                    }
        
        return comparison
    
    def get_credibility_ranking(self, min_analyses: int = 2) -> List[Dict]:
        """Get speakers ranked by credibility"""
        rankings = []
        
        for speaker, data in self.history.items():
            if len(data['analyses']) >= min_analyses:
                avg_credibility = sum(a['credibility_score'] for a in data['analyses']) / len(data['analyses'])
                rankings.append({
                    'speaker': speaker,
                    'average_credibility': avg_credibility,
                    'total_analyses': len(data['analyses']),
                    'false_claim_rate': data['false_claims'] / data['total_claims'] if data['total_claims'] > 0 else 0
                })
        
        return sorted(rankings, key=lambda x: x['average_credibility'], reverse=True)
