"""
Speaker History Tracker - Tracks fact-checking history for speakers
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict


class SpeakerHistoryTracker:
    """Track historical fact-checking data for speakers"""
    
    def __init__(self, data_file: str = "data/speaker_history.json"):
        self.data_file = data_file
        self.speaker_data: Dict[str, Dict[str, Any]] = {}
        self._load_data()
    
    def _load_data(self) -> None:
        """Load speaker history from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.speaker_data = json.load(f)
            except Exception:
                self.speaker_data = {}
        else:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            self.speaker_data = {}
    
    def _save_data(self) -> None:
        """Save speaker history to file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(self.speaker_data, f, indent=2)
        except Exception as e:
            print(f"Error saving speaker history: {e}")
    
    def get_speaker_history(self, speaker_name: str) -> Dict[str, Any]:
        """Get fact-checking history for a speaker"""
        if speaker_name not in self.speaker_data:
            return {
                'speaker': speaker_name,
                'total_claims': 0,
                'true_claims': 0,
                'false_claims': 0,
                'misleading_claims': 0,
                'unverified_claims': 0,
                'accuracy_rate': 0.0,
                'deception_rate': 0.0,
                'fact_checks': [],
                'patterns': {},
                'first_checked': None,
                'last_checked': None
            }
        
        return self.speaker_data[speaker_name]
    
    def add_fact_check_results(self, speaker_name: str, fact_checks: List[Dict[str, Any]], patterns: Dict[str, Any] = None) -> None:
        """Add new fact check results for a speaker"""
        if speaker_name not in self.speaker_data:
            self.speaker_data[speaker_name] = {
                'speaker': speaker_name,
                'total_claims': 0,
                'true_claims': 0,
                'false_claims': 0,
                'misleading_claims': 0,
                'intentionally_deceptive': 0,
                'unverified_claims': 0,
                'accuracy_rate': 0.0,
                'deception_rate': 0.0,
                'fact_checks': [],
                'patterns': defaultdict(int),
                'first_checked': datetime.now().isoformat(),
                'last_checked': datetime.now().isoformat()
            }
        
        speaker_info = self.speaker_data[speaker_name]
        
        # Update counts based on new fact checks
        for check in fact_checks:
            verdict = check.get('verdict', 'unverified').lower()
            
            speaker_info['total_claims'] += 1
            
            if verdict in ['true', 'mostly_true', 'nearly_true']:
                speaker_info['true_claims'] += 1
            elif verdict in ['false', 'mostly_false']:
                speaker_info['false_claims'] += 1
            elif verdict in ['misleading', 'exaggeration']:
                speaker_info['misleading_claims'] += 1
            elif verdict == 'intentionally_deceptive':
                speaker_info['intentionally_deceptive'] += 1
            else:
                speaker_info['unverified_claims'] += 1
            
            # Store fact check summary
            speaker_info['fact_checks'].append({
                'date': datetime.now().isoformat(),
                'claim': check.get('claim', ''),
                'verdict': verdict,
                'confidence': check.get('confidence', 0)
            })
        
        # Update patterns
        if patterns:
            for pattern, count in patterns.items():
                if isinstance(count, (int, float)):
                    speaker_info['patterns'][pattern] = speaker_info['patterns'].get(pattern, 0) + count
        
        # Calculate rates
        if speaker_info['total_claims'] > 0:
            speaker_info['accuracy_rate'] = (speaker_info['true_claims'] / speaker_info['total_claims']) * 100
            deceptive_claims = speaker_info['false_claims'] + speaker_info['misleading_claims'] + speaker_info['intentionally_deceptive']
            speaker_info['deception_rate'] = (deceptive_claims / speaker_info['total_claims']) * 100
        
        speaker_info['last_checked'] = datetime.now().isoformat()
        
        # Keep only last 100 fact checks
        if len(speaker_info['fact_checks']) > 100:
            speaker_info['fact_checks'] = speaker_info['fact_checks'][-100:]
        
        self._save_data()
    
    def update_speaker_record(self, speaker_name: str, record_data: Dict[str, Any]) -> None:
        """Update speaker record with additional information"""
        if speaker_name not in self.speaker_data:
            self.speaker_data[speaker_name] = self.get_speaker_history(speaker_name)
        
        # Update with new data
        self.speaker_data[speaker_name].update(record_data)
        self._save_data()
    
    def get_speaker_details(self, speaker_name: str) -> Dict[str, Any]:
        """Get detailed information about a speaker"""
        history = self.get_speaker_history(speaker_name)
        
        # Add additional analysis
        details = history.copy()
        
        if history['total_claims'] > 0:
            # Analyze patterns
            pattern_summary = []
            if history.get('patterns'):
                for pattern, count in history['patterns'].items():
                    if count > 2:  # Significant pattern
                        pattern_summary.append(f"{pattern}: {count} occurrences")
            
            details['pattern_summary'] = pattern_summary
            
            # Credibility assessment
            if history['accuracy_rate'] >= 80:
                details['credibility'] = 'High'
            elif history['accuracy_rate'] >= 60:
                details['credibility'] = 'Medium'
            else:
                details['credibility'] = 'Low'
            
            # Deception assessment
            if history['deception_rate'] >= 50:
                details['deception_level'] = 'High'
            elif history['deception_rate'] >= 25:
                details['deception_level'] = 'Medium'
            else:
                details['deception_level'] = 'Low'
        
        return details
    
    def get_all_speakers(self) -> List[Dict[str, Any]]:
        """Get list of all speakers with their summary data"""
        speakers = []
        
        for speaker_name, data in self.speaker_data.items():
            speakers.append({
                'name': speaker_name,
                'total_claims': data.get('total_claims', 0),
                'accuracy_rate': data.get('accuracy_rate', 0),
                'deception_rate': data.get('deception_rate', 0),
                'last_checked': data.get('last_checked')
            })
        
        # Sort by total claims (most active speakers first)
        speakers.sort(key=lambda x: x['total_claims'], reverse=True)
        
        return speakers
    
    def compare_speakers(self, speaker_names: List[str]) -> Dict[str, Any]:
        """Compare multiple speakers"""
        comparison = {
            'speakers': {},
            'summary': {}
        }
        
        for speaker in speaker_names:
            comparison['speakers'][speaker] = self.get_speaker_details(speaker)
        
        # Calculate summary statistics
        if comparison['speakers']:
            avg_accuracy = sum(s.get('accuracy_rate', 0) for s in comparison['speakers'].values()) / len(speaker_names)
            avg_deception = sum(s.get('deception_rate', 0) for s in comparison['speakers'].values()) / len(speaker_names)
            
            comparison['summary'] = {
                'average_accuracy': avg_accuracy,
                'average_deception': avg_deception,
                'most_accurate': max(comparison['speakers'].items(), key=lambda x: x[1].get('accuracy_rate', 0))[0],
                'least_accurate': min(comparison['speakers'].items(), key=lambda x: x[1].get('accuracy_rate', 0))[0]
            }
        
        return comparison
