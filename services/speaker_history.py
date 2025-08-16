"""
Speaker History Tracking Module - Enhanced with Better Speaker Identification
Tracks historical patterns and credibility of speakers/sources
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import logging
import re

logger = logging.getLogger(__name__)

class SpeakerHistoryTracker:
    """Track and analyze speaker credibility history"""
    
    def __init__(self, storage_path: str = "data/speaker_history.json"):
        self.storage_path = storage_path
        self.history = self._load_history()
        
        # Enhanced speaker patterns with roles
        self.speaker_patterns = {
            # Press Secretaries
            'kayleigh mcenany': {
                'name': 'Kayleigh McEnany',
                'role': 'Former White House Press Secretary (Trump)',
                'party': 'Republican'
            },
            'karine jean-pierre': {
                'name': 'Karine Jean-Pierre', 
                'role': 'White House Press Secretary (Biden)',
                'party': 'Democrat'
            },
            'jen psaki': {
                'name': 'Jen Psaki',
                'role': 'Former White House Press Secretary (Biden)',
                'party': 'Democrat'
            },
            'sarah huckabee sanders': {
                'name': 'Sarah Huckabee Sanders',
                'role': 'Former White House Press Secretary (Trump)',
                'party': 'Republican'
            },
            'sean spicer': {
                'name': 'Sean Spicer',
                'role': 'Former White House Press Secretary (Trump)',
                'party': 'Republican'
            },
            
            # Presidents and VPs
            'donald trump': {
                'name': 'Donald Trump',
                'role': 'Former President',
                'party': 'Republican'
            },
            'joe biden': {
                'name': 'Joe Biden',
                'role': 'President',
                'party': 'Democrat'
            },
            'kamala harris': {
                'name': 'Kamala Harris',
                'role': 'Vice President',
                'party': 'Democrat'
            },
            'mike pence': {
                'name': 'Mike Pence',
                'role': 'Former Vice President',
                'party': 'Republican'
            },
            
            # Cabinet Members
            'alejandro mayorkas': {
                'name': 'Alejandro Mayorkas',
                'role': 'Secretary of Homeland Security',
                'party': 'Democrat'
            },
            'antony blinken': {
                'name': 'Antony Blinken',
                'role': 'Secretary of State',
                'party': 'Democrat'
            },
            'janet yellen': {
                'name': 'Janet Yellen',
                'role': 'Secretary of Treasury',
                'party': 'Democrat'
            },
            'lloyd austin': {
                'name': 'Lloyd Austin',
                'role': 'Secretary of Defense',
                'party': 'Democrat'
            },
            
            # Senators
            'bernie sanders': {
                'name': 'Bernie Sanders',
                'role': 'Senator (Vermont)',
                'party': 'Independent'
            },
            'ted cruz': {
                'name': 'Ted Cruz',
                'role': 'Senator (Texas)',
                'party': 'Republican'
            },
            'elizabeth warren': {
                'name': 'Elizabeth Warren',
                'role': 'Senator (Massachusetts)',
                'party': 'Democrat'
            },
            'marco rubio': {
                'name': 'Marco Rubio',
                'role': 'Senator (Florida)',
                'party': 'Republican'
            },
            
            # Governors
            'ron desantis': {
                'name': 'Ron DeSantis',
                'role': 'Governor of Florida',
                'party': 'Republican'
            },
            'gavin newsom': {
                'name': 'Gavin Newsom',
                'role': 'Governor of California',
                'party': 'Democrat'
            },
            'greg abbott': {
                'name': 'Greg Abbott',
                'role': 'Governor of Texas',
                'party': 'Republican'
            }
        }
        
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
        """Extract speaker identity from source and transcript - ENHANCED"""
        source_lower = source.lower()
        transcript_lower = transcript.lower()
        
        # First, check for explicit speaker identification in source
        logger.info(f"Extracting speaker from source: {source}")
        
        # Look for patterns like "Press Secretary Kayleigh McEnany"
        role_patterns = [
            r'(?:press secretary|spokesperson|secretary|senator|representative|governor|president|vice president)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+(?:press secretary|spokesperson|secretary|senator|representative|governor)',
            r'statement (?:by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'remarks (?:by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:speaks|speaking|announces|announcing)',
        ]
        
        # Check source for speaker name
        for pattern in role_patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                logger.info(f"Found potential speaker in source: {potential_name}")
                
                # Check against known speakers
                potential_lower = potential_name.lower()
                for known_key, known_info in self.speaker_patterns.items():
                    if potential_lower in known_key or known_key in potential_lower:
                        logger.info(f"Matched to known speaker: {known_info['name']} ({known_info['role']})")
                        return known_info['name']
                
                # If not in known speakers but looks like a name, return it
                if len(potential_name.split()) >= 2:
                    return potential_name
        
        # Check transcript for self-identification
        self_id_patterns = [
            r"(?:i'm|i am|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+here,?\s+(?:and|speaking)",
            r"this is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        
        for pattern in self_id_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                logger.info(f"Found self-identification: {potential_name}")
                
                # Check against known speakers
                potential_lower = potential_name.lower()
                for known_key, known_info in self.speaker_patterns.items():
                    if potential_lower in known_key or known_key in potential_lower:
                        return known_info['name']
                
                if len(potential_name.split()) >= 2:
                    return potential_name
        
        # Last resort: check for known speaker names in source/transcript
        for key, info in self.speaker_patterns.items():
            if key in source_lower:
                logger.info(f"Found known speaker {info['name']} in source")
                return info['name']
        
        # Check for press conference or briefing
        if any(term in source_lower for term in ['press briefing', 'press conference', 'white house briefing']):
            # Try to identify administration
            if 'biden' in source_lower or 'biden' in transcript_lower[:500]:
                return 'Karine Jean-Pierre'  # Current press secretary
            elif 'trump' in source_lower or 'trump' in transcript_lower[:500]:
                # Could be any of Trump's press secretaries
                if 'kayleigh' in source_lower or 'mcenany' in source_lower:
                    return 'Kayleigh McEnany'
                elif 'sarah' in source_lower or 'sanders' in source_lower:
                    return 'Sarah Huckabee Sanders'
                elif 'spicer' in source_lower:
                    return 'Sean Spicer'
        
        logger.info("Could not identify specific speaker")
        return None
    
    def get_speaker_info(self, speaker_name: str) -> Optional[Dict]:
        """Get detailed info about a speaker"""
        speaker_lower = speaker_name.lower()
        
        for key, info in self.speaker_patterns.items():
            if speaker_lower in key or key in speaker_lower:
                return info
        
        return None
    
    def add_analysis(self, speaker: str, analysis_results: Dict):
        """Add a new analysis to speaker history"""
        if not speaker:
            return
        
        # Get speaker info if available
        speaker_info = self.get_speaker_info(speaker)
        
        if speaker not in self.history:
            self.history[speaker] = {
                'first_analyzed': datetime.now().isoformat(),
                'analyses': [],
                'total_claims': 0,
                'false_claims': 0,
                'misleading_claims': 0,
                'true_claims': 0,
                'patterns': [],
                'info': speaker_info  # Store role/party info
            }
        
        # Extract key metrics
        false_count = sum(1 for fc in analysis_results['fact_checks'] 
                         if fc.get('verdict') in ['false', 'mostly_false'])
        misleading_count = sum(1 for fc in analysis_results['fact_checks'] 
                              if fc.get('verdict') in ['misleading', 'deceptive'])
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
        
        summary = {
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
        
        # Add speaker info if available
        if data.get('info'):
            summary['role'] = data['info'].get('role')
            summary['party'] = data['info'].get('party')
        
        return summary
    
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
                        'total_analyses': summary['total_analyses'],
                        'role': summary.get('role', 'Unknown'),
                        'party': summary.get('party', 'Unknown')
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
                    'false_claim_rate': data['false_claims'] / data['total_claims'] if data['total_claims'] > 0 else 0,
                    'role': data.get('info', {}).get('role', 'Unknown'),
                    'party': data.get('info', {}).get('party', 'Unknown')
                })
        
        return sorted(rankings, key=lambda x: x['average_credibility'], reverse=True)
