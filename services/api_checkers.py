# services/api_checkers.py  
"""
API Checker Modules - Complete implementation
Individual API checking methods for various fact-checking sources
"""
import re
import logging
import aiohttp
import json
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class APICheckers:
    """Collection of API checking methods"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.google_api_key = api_keys.get('google')
        self.fred_api_key = api_keys.get('fred')
        self.openai_api_key = api_keys.get('openai')
        self.mediastack_api_key = api_keys.get('mediastack')
        self.news_api_key = api_keys.get('news')
        self.noaa_token = api_keys.get('noaa')
        self.crossref_email = api_keys.get('crossref_email', 'factchecker@example.com')
        
        # FRED series mapping
        self.fred_series = {
            'unemployment': 'UNRATE',
            'inflation': 'CPIAUCSL',
            'gdp': 'GDP',
            'interest rate': 'DFF',
            'federal funds': 'DFF',
            'jobs': 'PAYEMS',
            'employment': 'PAYEMS',
            'retail sales': 'RSXFS',
            'housing starts': 'HOUST',
            'consumer confidence': 'UMCSENT',
            'manufacturing': 'IPMAN',
            'recession': 'USREC'
        }
    
    async def check_google_factcheck(self, claim: str) -> Dict:
        """Check Google Fact Check API"""
        if not self.google_api_key:
            return {'found': False}
        
        try:
            params = {
                'key': self.google_api_key,
                'query': claim[:200],
                'languageCode': 'en'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://factchecktools.googleapis.com/v1alpha1/claims:search',
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('claims'):
                            claim_data = data['claims'][0]
                            review = claim_data.get('claimReview', [{}])[0]
                            
                            return {
                                'found': True,
                                'verdict': self._parse_google_verdict(review.get('textualRating', '')),
                                'explanation': review.get('text', 'Fact-check available from Google Fact Check API'),
                                'confidence': 80,
                                'source': review.get('publisher', {}).get('name', 'Google Fact Check'),
                                'url': review.get('url', '')
                            }
                        
                    return {'found': False}
                    
        except Exception as e:
            logger.error(f"Google Fact Check API error: {e}")
            return {'found': False}
    
    def _parse_google_verdict(self, textual_rating: str) -> str:
        """Parse Google's textual rating to our verdict system"""
        if not textual_rating:
            return 'needs_context'
        
        rating_lower = textual_rating.lower()
        
        if any(word in rating_lower for word in ['true', 'correct', 'accurate']):
            return 'true'
        elif any(word in rating_lower for word in ['mostly true', 'largely accurate']):
            return 'mostly_true'
        elif any(word in rating_lower for word in ['mixed', 'half true']):
            return 'exaggeration'
        elif any(word in rating_lower for word in ['misleading', 'distorts']):
            return 'misleading'
        elif any(word in rating_lower for word in ['mostly false', 'largely inaccurate']):
            return 'mostly_false'
        elif any(word in rating_lower for word in ['false', 'incorrect', 'wrong']):
            return 'false'
        else:
            return 'needs_context'
    
    async def check_fred_data(self, claim: str) -> Dict:
        """Check economic claims against FRED data"""
        if not self.fred_api_key:
            return {'found': False}
        
        try:
            # Extract potential economic indicators
            claim_lower = claim.lower()
            
            for keyword, series_id in self.fred_series.items():
                if keyword in claim_lower:
                    # Get recent data for this series
                    async with aiohttp.ClientSession() as session:
                        url = f"https://api.stlouisfed.org/fred/series/observations"
                        params = {
                            'series_id': series_id,
                            'api_key': self.fred_api_key,
                            'file_type': 'json',
                            'limit': 12,  # Last 12 observations
                            'sort_order': 'desc'
                        }
                        
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                observations = data.get('observations', [])
                                
                                if observations:
                                    latest = observations[0]
                                    return {
                                        'found': True,
                                        'verdict': 'needs_context',
                                        'explanation': f"Latest {keyword} data from FRED: {latest.get('value')} as of {latest.get('date')}",
                                        'confidence': 75,
                                        'source': 'Federal Reserve Economic Data (FRED)',
                                        'data': observations
                                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"FRED API error: {e}")
            return {'found': False}
    
    async def check_news_apis(self, claim: str) -> Dict:
        """Check claim against news APIs for recent verification"""
        if not self.news_api_key and not self.mediastack_api_key:
            return {'found': False}
        
        try:
            # Use NewsAPI if available
            if self.news_api_key:
                return await self._check_newsapi(claim)
            
            # Fallback to MediaStack
            elif self.mediastack_api_key:
                return await self._check_mediastack(claim)
                
        except Exception as e:
            logger.error(f"News API error: {e}")
            return {'found': False}
    
    async def _check_newsapi(self, claim: str) -> Dict:
        """Check NewsAPI for related articles"""
        try:
            # Extract key terms from claim
            key_terms = self._extract_key_terms(claim)
            if not key_terms:
                return {'found': False}
            
            query = ' AND '.join(key_terms[:3])  # Use top 3 terms
            
            async with aiohttp.ClientSession() as session:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': query,
                    'apiKey': self.news_api_key,
                    'language': 'en',
                    'sortBy': 'relevancy',
                    'pageSize': 5
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('articles', [])
                        
                        if articles:
                            return {
                                'found': True,
                                'verdict': 'needs_context',
                                'explanation': f"Found {len(articles)} recent news articles related to this claim",
                                'confidence': 60,
                                'source': 'NewsAPI',
                                'articles': [{'title': a['title'], 'url': a['url']} for a in articles[:3]]
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return {'found': False}
    
    async def _check_mediastack(self, claim: str) -> Dict:
        """Check MediaStack API for related news"""
        try:
            key_terms = self._extract_key_terms(claim)
            if not key_terms:
                return {'found': False}
            
            query = ' '.join(key_terms[:3])
            
            async with aiohttp.ClientSession() as session:
                url = "http://api.mediastack.com/v1/news"
                params = {
                    'access_key': self.mediastack_api_key,
                    'keywords': query,
                    'languages': 'en',
                    'limit': 5
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('data', [])
                        
                        if articles:
                            return {
                                'found': True,
                                'verdict': 'needs_context',
                                'explanation': f"Found {len(articles)} recent articles from MediaStack",
                                'confidence': 60,
                                'source': 'MediaStack',
                                'articles': [{'title': a['title'], 'url': a['url']} for a in articles[:3]]
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"MediaStack error: {e}")
            return {'found': False}
    
    def _extract_key_terms(self, claim: str) -> List[str]:
        """Extract key terms from claim for search"""
        # Remove common words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall'
        }
        
        # Extract words, remove punctuation
        words = re.findall(r'\b[a-zA-Z]+\b', claim.lower())
        
        # Filter out stop words and short words
        key_terms = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Return unique terms, prioritizing longer ones
        return list(dict.fromkeys(sorted(key_terms, key=len, reverse=True)))


# services/context_resolver.py
"""
Context Resolver Module - Enhanced context resolution for claims
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ContextResolver:
    """Resolve context and pronouns in claims"""
    
    def __init__(self):
        self.pronouns = {
            'he': ['speaker', 'subject'],
            'she': ['speaker', 'subject'], 
            'they': ['group', 'organization'],
            'we': ['group', 'organization'],
            'it': ['organization', 'policy', 'thing'],
            'this': ['policy', 'event', 'thing'],
            'that': ['policy', 'event', 'thing']
        }
    
    def resolve_with_context(self, claim: str, context: Optional[Dict] = None) -> Tuple[str, Dict]:
        """Resolve pronouns and context in claim"""
        if not context:
            return claim, {}
        
        resolved_claim = claim
        resolution_info = {}
        
        # Get transcript and speaker context
        transcript = context.get('transcript', '')
        speaker = context.get('speaker', 'Unknown')
        
        # Simple pronoun resolution based on speaker
        if speaker != 'Unknown':
            resolved_claim = self._resolve_pronouns(resolved_claim, speaker)
            resolution_info['speaker_resolved'] = speaker
        
        # Add more context from transcript if available
        if transcript and len(resolved_claim) < len(claim) + 50:
            context_addition = self._extract_nearby_context(claim, transcript)
            if context_addition:
                resolution_info['context_addition'] = context_addition
        
        return resolved_claim, resolution_info
    
    def _resolve_pronouns(self, claim: str, speaker: str) -> str:
        """Basic pronoun resolution"""
        # Simple replacements - could be enhanced with NLP
        resolved = claim
        
        # Replace common pronouns with speaker name
        resolved = re.sub(r'\bI\b', speaker, resolved)
        resolved = re.sub(r'\bmy\b', f"{speaker}'s", resolved)
        resolved = re.sub(r'\bmine\b', f"{speaker}'s", resolved)
        
        return resolved
    
    def _extract_nearby_context(self, claim: str, transcript: str) -> Optional[str]:
        """Extract nearby context from transcript"""
        # Find the claim in transcript and get surrounding context
        claim_words = claim.lower().split()[:5]  # First 5 words
        
        if len(claim_words) < 2:
            return None
        
        search_phrase = ' '.join(claim_words)
        transcript_lower = transcript.lower()
        
        # Find approximate location
        pos = transcript_lower.find(search_phrase)
        if pos != -1:
            # Get some context before and after
            start = max(0, pos - 100)
            end = min(len(transcript), pos + len(claim) + 100)
            context = transcript[start:end].strip()
            
            if context and len(context) > len(claim):
                return context
        
        return None


# services/factcheck_history.py
"""
Fact Check History Tracking Module
Tracks historical claims and patterns for better context
"""
import re
import hashlib
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
        """Create hash for claim deduplication"""
        # Normalize claim text
        normalized = re.sub(r'[^\w\s]', '', claim.lower().strip())
        normalized = ' '.join(normalized.split())  # Normalize whitespace
        
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def get_pattern_analysis(self, source: str) -> Dict:
        """Analyze patterns for a specific source"""
        if source not in self.source_patterns:
            return {'pattern': 'unknown', 'confidence': 0}
        
        stats = self.source_patterns[source]
        total = sum(stats.values())
        
        if total < 5:  # Not enough data
            return {'pattern': 'insufficient_data', 'confidence': 0}
        
        false_rate = (stats.get('false', 0) + stats.get('mostly_false', 0)) / total
        misleading_rate = stats.get('misleading', 0) / total
        true_rate = (stats.get('true', 0) + stats.get('mostly_true', 0)) / total
        
        if false_rate > 0.6:
            return {'pattern': 'frequently_false', 'confidence': 85}
        elif misleading_rate > 0.5:
            return {'pattern': 'often_misleading', 'confidence': 75}
        elif true_rate > 0.7:
            return {'pattern': 'generally_accurate', 'confidence': 80}
        else:
            return {'pattern': 'mixed_accuracy', 'confidence': 60}# services/context_resolver.py
"""
Context Resolver Module - Enhanced context resolution for claims
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ContextResolver:
    """Resolve context and pronouns in claims"""
    
    def __init__(self):
        self.pronouns = {
            'he': ['speaker', 'subject'],
            'she': ['speaker', 'subject'], 
            'they': ['group', 'organization'],
            'we': ['group', 'organization'],
            'it': ['organization', 'policy', 'thing'],
            'this': ['policy', 'event', 'thing'],
            'that': ['policy', 'event', 'thing']
        }
    
    def resolve_with_context(self, claim: str, context: Optional[Dict] = None) -> Tuple[str, Dict]:
        """Resolve pronouns and context in claim"""
        if not context:
            return claim, {}
        
        resolved_claim = claim
        resolution_info = {}
        
        # Get transcript and speaker context
        transcript = context.get('transcript', '')
        speaker = context.get('speaker', 'Unknown')
        
        # Simple pronoun resolution based on speaker
        if speaker != 'Unknown':
            resolved_claim = self._resolve_pronouns(resolved_claim, speaker)
            resolution_info['speaker_resolved'] = speaker
        
        # Add more context from transcript if available
        if transcript and len(resolved_claim) < len(claim) + 50:
            context_addition = self._extract_nearby_context(claim, transcript)
            if context_addition:
                resolution_info['context_addition'] = context_addition
        
        return resolved_claim, resolution_info
    
    def _resolve_pronouns(self, claim: str, speaker: str) -> str:
        """Basic pronoun resolution"""
        # Simple replacements - could be enhanced with NLP
        resolved = claim
        
        # Replace common pronouns with speaker name
        resolved = re.sub(r'\bI\b', speaker, resolved)
        resolved = re.sub(r'\bmy\b', f"{speaker}'s", resolved)
        resolved = re.sub(r'\bmine\b', f"{speaker}'s", resolved)
        
        return resolved
    
    def _extract_nearby_context(self, claim: str, transcript: str) -> Optional[str]:
        """Extract nearby context from transcript"""
        # Find the claim in transcript and get surrounding context
        claim_words = claim.lower().split()[:5]  # First 5 words
        
        if len(claim_words) < 2:
            return None
        
        search_phrase = ' '.join(claim_words)
        transcript_lower = transcript.lower()
        
        # Find approximate location
        pos = transcript_lower.find(search_phrase)
        if pos != -1:
            # Get some context before and after
            start = max(0, pos - 100)
            end = min(len(transcript), pos + len(claim) + 100)
            context = transcript[start:end].strip()
            
            if context and len(context) > len(claim):
                return context
        
        return None


# services/factcheck_history.py
"""
Fact Check History Tracking Module
Tracks historical claims and patterns for better context
"""
import re
import hashlib
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
        """Create hash for claim deduplication"""
        # Normalize claim text
        normalized = re.sub(r'[^\w\s]', '', claim.lower().strip())
        normalized = ' '.join(normalized.split())  # Normalize whitespace
        
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def get_pattern_analysis(self, source: str) -> Dict:
        """Analyze patterns for a specific source"""
        if source not in self.source_patterns:
            return {'pattern': 'unknown', 'confidence': 0}
        
        stats = self.source_patterns[source]
        total = sum(stats.values())
        
        if total < 5:  # Not enough data
            return {'pattern': 'insufficient_data', 'confidence': 0}
        
        false_rate = (stats.get('false', 0) + stats.get('mostly_false', 0)) / total
        misleading_rate = stats.get('misleading', 0) / total
        true_rate = (stats.get('true', 0) + stats.get('mostly_true', 0)) / total
        
        if false_rate > 0.6:
            return {'pattern': 'frequently_false', 'confidence': 85}
        elif misleading_rate > 0.5:
            return {'pattern': 'often_misleading', 'confidence': 75}
        elif true_rate > 0.7:
            return {'pattern': 'generally_accurate', 'confidence': 80}
        else:
            return {'pattern': 'mixed_accuracy', 'confidence': 60}
