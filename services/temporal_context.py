"""
Temporal Context Handler
Properly handles time references in transcripts
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

class TemporalContextHandler:
    """Handle temporal references in claims based on source context"""
    
    def __init__(self):
        self.temporal_patterns = {
            # Relative time references
            'this_week': r'\bthis\s+week\b',
            'last_week': r'\blast\s+week\b',
            'next_week': r'\bnext\s+week\b',
            'yesterday': r'\byesterday\b',
            'today': r'\btoday\b',
            'tomorrow': r'\btomorrow\b',
            'this_month': r'\bthis\s+month\b',
            'last_month': r'\blast\s+month\b',
            'this_year': r'\bthis\s+year\b',
            'last_year': r'\blast\s+year\b',
            'recently': r'\brecently\b',
            'soon': r'\bsoon\b',
            'this_morning': r'\bthis\s+morning\b',
            'this_afternoon': r'\bthis\s+afternoon\b',
            'this_evening': r'\bthis\s+evening\b',
            'tonight': r'\btonight\b',
            'last_night': r'\blast\s+night\b',
        }
        
        self.months = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
    
    def extract_source_date(self, source: str) -> Optional[datetime]:
        """Extract date from source information"""
        # YouTube pattern: "YouTube: Title (uploaded on DATE)"
        youtube_pattern = r'uploaded on (\w+ \d+, \d{4})'
        match = re.search(youtube_pattern, source)
        if match:
            try:
                return datetime.strptime(match.group(1), '%B %d, %Y')
            except:
                pass
        
        # Look for dates in various formats
        date_patterns = [
            (r'(\d{1,2}/\d{1,2}/\d{4})', '%m/%d/%Y'),
            (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
            (r'(\w+ \d+, \d{4})', '%B %d, %Y'),
            (r'(\d+ \w+ \d{4})', '%d %B %Y'),
        ]
        
        for pattern, format_str in date_patterns:
            match = re.search(pattern, source)
            if match:
                try:
                    return datetime.strptime(match.group(1), format_str)
                except:
                    continue
        
        return None
    
    def contextualize_claim(self, claim: str, source: str, source_date: Optional[datetime] = None) -> Tuple[str, Dict]:
        """Add temporal context to claims"""
        claim_lower = claim.lower()
        context_info = {
            'original_claim': claim,
            'has_temporal_reference': False,
            'temporal_adjustments': []
        }
        
        # If no source date, try to extract it
        if not source_date:
            source_date = self.extract_source_date(source)
        
        # Check for temporal references
        temporal_refs_found = []
        for ref_type, pattern in self.temporal_patterns.items():
            if re.search(pattern, claim_lower):
                temporal_refs_found.append(ref_type)
                context_info['has_temporal_reference'] = True
        
        if not temporal_refs_found:
            return claim, context_info
        
        # Add context based on source date
        if source_date:
            context_info['source_date'] = source_date.strftime('%B %d, %Y')
            
            # Calculate what the temporal references mean
            for ref in temporal_refs_found:
                if ref == 'this_week':
                    week_start = source_date - timedelta(days=source_date.weekday())
                    week_end = week_start + timedelta(days=6)
                    context_info['temporal_adjustments'].append({
                        'reference': 'this week',
                        'actual_period': f"{week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
                    })
                    
                elif ref == 'yesterday':
                    yesterday = source_date - timedelta(days=1)
                    context_info['temporal_adjustments'].append({
                        'reference': 'yesterday',
                        'actual_date': yesterday.strftime('%B %d, %Y')
                    })
                    
                elif ref == 'today':
                    context_info['temporal_adjustments'].append({
                        'reference': 'today',
                        'actual_date': source_date.strftime('%B %d, %Y')
                    })
                    
                elif ref == 'last_week':
                    last_week_end = source_date - timedelta(days=source_date.weekday() + 1)
                    last_week_start = last_week_end - timedelta(days=6)
                    context_info['temporal_adjustments'].append({
                        'reference': 'last week',
                        'actual_period': f"{last_week_start.strftime('%B %d')} - {last_week_end.strftime('%B %d, %Y')}"
                    })
                    
                elif ref == 'this_month':
                    context_info['temporal_adjustments'].append({
                        'reference': 'this month',
                        'actual_month': source_date.strftime('%B %Y')
                    })
                    
                elif ref == 'last_month':
                    if source_date.month == 1:
                        last_month = source_date.replace(year=source_date.year - 1, month=12)
                    else:
                        last_month = source_date.replace(month=source_date.month - 1)
                    context_info['temporal_adjustments'].append({
                        'reference': 'last month',
                        'actual_month': last_month.strftime('%B %Y')
                    })
                    
                elif ref == 'this_year':
                    context_info['temporal_adjustments'].append({
                        'reference': 'this year',
                        'actual_year': str(source_date.year)
                    })
                    
                elif ref == 'last_year':
                    context_info['temporal_adjustments'].append({
                        'reference': 'last year',
                        'actual_year': str(source_date.year - 1)
                    })
                    
                elif ref == 'recently':
                    # "Recently" typically means within the last few weeks/months
                    context_info['temporal_adjustments'].append({
                        'reference': 'recently',
                        'context': f"relative to {source_date.strftime('%B %Y')}"
                    })
        
        else:
            # No source date available - add generic warning
            context_info['temporal_warning'] = 'Temporal references detected but source date unknown'
        
        return claim, context_info
    
    def create_temporal_context_note(self, context_info: Dict) -> Optional[str]:
        """Create a human-readable temporal context note"""
        if not context_info.get('has_temporal_reference'):
            return None
        
        if context_info.get('temporal_warning'):
            return context_info['temporal_warning']
        
        if not context_info.get('temporal_adjustments'):
            return None
        
        # Build context note
        notes = []
        for adjustment in context_info['temporal_adjustments']:
            ref = adjustment['reference']
            if 'actual_date' in adjustment:
                notes.append(f'"{ref}" refers to {adjustment["actual_date"]}')
            elif 'actual_period' in adjustment:
                notes.append(f'"{ref}" refers to {adjustment["actual_period"]}')
            elif 'actual_month' in adjustment:
                notes.append(f'"{ref}" refers to {adjustment["actual_month"]}')
            elif 'actual_year' in adjustment:
                notes.append(f'"{ref}" refers to {adjustment["actual_year"]}')
            elif 'context' in adjustment:
                notes.append(f'"{ref}" is {adjustment["context"]}')
        
        if notes:
            source_date = context_info.get('source_date', 'unknown date')
            return f"Based on source date ({source_date}): " + "; ".join(notes)
        
        return None
    
    def adjust_claim_for_checking(self, claim: str, context_info: Dict) -> str:
        """Adjust claim text to include temporal context for fact-checking"""
        if not context_info.get('temporal_adjustments'):
            return claim
        
        adjusted_claim = claim
        
        # Replace temporal references with specific dates/periods
        for adjustment in context_info['temporal_adjustments']:
            ref = adjustment['reference']
            
            if 'actual_date' in adjustment:
                # Replace with specific date
                pattern = self.temporal_patterns.get(ref.replace(' ', '_'))
                if pattern:
                    adjusted_claim = re.sub(
                        pattern, 
                        f"on {adjustment['actual_date']}", 
                        adjusted_claim, 
                        flags=re.IGNORECASE
                    )
                    
            elif 'actual_period' in adjustment:
                # Replace with specific period
                pattern = self.temporal_patterns.get(ref.replace(' ', '_'))
                if pattern:
                    adjusted_claim = re.sub(
                        pattern, 
                        f"during {adjustment['actual_period']}", 
                        adjusted_claim, 
                        flags=re.IGNORECASE
                    )
                    
            elif 'actual_month' in adjustment:
                # Replace with specific month
                pattern = self.temporal_patterns.get(ref.replace(' ', '_'))
                if pattern:
                    adjusted_claim = re.sub(
                        pattern, 
                        f"in {adjustment['actual_month']}", 
                        adjusted_claim, 
                        flags=re.IGNORECASE
                    )
                    
            elif 'actual_year' in adjustment:
                # Replace with specific year
                pattern = self.temporal_patterns.get(ref.replace(' ', '_'))
                if pattern:
                    adjusted_claim = re.sub(
                        pattern, 
                        f"in {adjustment['actual_year']}", 
                        adjusted_claim, 
                        flags=re.IGNORECASE
                    )
        
        logger.info(f"Adjusted claim from '{claim}' to '{adjusted_claim}'")
        return adjusted_claim
    
    def process_claims_with_temporal_context(self, claims: List[Dict], source: str) -> List[Dict]:
        """Process a list of claims and add temporal context"""
        source_date = self.extract_source_date(source)
        
        if source_date:
            logger.info(f"Extracted source date: {source_date.strftime('%B %d, %Y')}")
        else:
            logger.info("No source date found, temporal references will be noted but not adjusted")
        
        processed_claims = []
        
        for claim_data in claims:
            if isinstance(claim_data, dict):
                claim_text = claim_data.get('text', '')
            else:
                claim_text = str(claim_data)
                claim_data = {'text': claim_text}
            
            # Contextualize the claim
            contextualized_claim, context_info = self.contextualize_claim(
                claim_text, source, source_date
            )
            
            # Create adjusted claim for fact-checking
            adjusted_claim = self.adjust_claim_for_checking(claim_text, context_info)
            
            # Add temporal context note
            temporal_note = self.create_temporal_context_note(context_info)
            
            # Update claim data
            claim_data['original_text'] = claim_text
            claim_data['text'] = adjusted_claim  # Use adjusted text for fact-checking
            claim_data['temporal_context'] = context_info
            claim_data['temporal_note'] = temporal_note
            
            processed_claims.append(claim_data)
        
        return processed_claims
