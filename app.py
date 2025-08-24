"""
Comprehensive Fact-Checking Service that uses ALL available APIs
"""
import re
import logging
import requests
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

# Import all our services
from .api_checkers import APICheckers
from .context_resolver import ContextResolver
from .factcheck_history import FactCheckHistory

logger = logging.getLogger(__name__)

# Keep the verdict categories from original
VERDICT_CATEGORIES = {
    'true': {
        'label': 'True',
        'icon': '✅',
        'color': '#10b981',
        'score': 100,
        'description': 'The claim is accurate and supported by evidence'
    },
    'mostly_true': {
        'label': 'Mostly True',
        'icon': '✓',
        'color': '#34d399',
        'score': 85,
        'description': 'The claim is largely accurate with minor imprecision'
    },
    'nearly_true': {
        'label': 'Nearly True',
        'icon': '🔵',
        'color': '#6ee7b7',
        'score': 70,
        'description': 'Largely accurate but missing some context'
    },
    'exaggeration': {
        'label': 'Exaggeration',
        'icon': '📏',
        'color': '#fbbf24',
        'score': 50,
        'description': 'Based on truth but overstated'
    },
    'misleading': {
        'label': 'Misleading',
        'icon': '⚠️',
        'color': '#f59e0b',
        'score': 35,
        'description': 'Contains truth but creates false impression'
    },
    'mostly_false': {
        'label': 'Mostly False',
        'icon': '❌',
        'color': '#f87171',
        'score': 20,
        'description': 'Significant inaccuracies with grain of truth'
    },
    'false': {
        'label': 'False',
        'icon': '❌',
        'color': '#ef4444',
        'score': 0,
        'description': 'Demonstrably incorrect'
    },
    'needs_context': {
        'label': 'Needs Context',
        'icon': '❓',
        'color': '#8b5cf6',
        'score': None,
        'description': 'Cannot verify without additional information'
    },
    'opinion': {
        'label': 'Opinion',
        'icon': '💭',
        'color': '#6366f1',
        'score': None,
        'description': 'Subjective statement, not a factual claim'
    }
}

class ComprehensiveFactChecker:
    """Enhanced fact-checking that actually uses all available services"""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize all API keys (excluding scraper)
        self.api_keys = {
            'google': getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None),
            'openai': getattr(config, 'OPENAI_API_KEY', None),
            'fred': getattr(config, 'FRED_API_KEY', None),
            'news': getattr(config, 'NEWS_API_KEY', None),
            'mediastack': getattr(config, 'MEDIASTACK_API_KEY', None),
            'noaa': getattr(config, 'NOAA_TOKEN', None),
            'census': getattr(config, 'CENSUS_API_KEY', None),
            'cdc': getattr(config, 'CDC_API_KEY', None),
        }
        
        # Initialize services
        self.api_checkers = APICheckers(self.api_keys)
        self.context_resolver = ContextResolver()
        self.fact_history = FactCheckHistory()
        
        # Initialize OpenAI if available
        self.openai_client = None
        if self.api_keys['openai']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.api_keys['openai'])
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Thread pool for parallel API calls
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Main entry point - check claim using ALL available resources"""
        try:
            # Clean claim
            claim = claim.strip()
            
            # Skip if too short or opinion
            if len(claim.split()) < 4:
                return self._create_verdict('opinion', 'Statement too short to fact-check')
            
            if self._is_pure_opinion(claim):
                return self._create_verdict('opinion', 'This is a subjective opinion')
            
            # Resolve context (pronouns, references)
            if context and context.get('transcript'):
                self.context_resolver.analyze_full_transcript(context['transcript'])
            
            resolved_claim, context_info = self.context_resolver.resolve_context(claim)
            if resolved_claim != claim:
                logger.info(f"Resolved claim: {claim} -> {resolved_claim}")
                claim = resolved_claim
            
            # Check if claim is too vague
            vagueness = self.context_resolver.is_claim_too_vague(claim)
            if vagueness['is_vague']:
                return self._create_verdict('needs_context', vagueness['reason'])
            
            # Check historical patterns
            speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            historical = self.fact_history.get_historical_context(claim, speaker)
            
            # Run comprehensive fact-checking
            result = asyncio.run(self._comprehensive_check(claim, speaker, historical))
            
            # Add to history
            self.fact_history.add_check(claim, speaker, result['verdict'], result['explanation'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fact-check: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    async def _comprehensive_check(self, claim: str, speaker: str, historical: Optional[Dict]) -> Dict:
        """Run all fact-checking methods in parallel"""
        
        # Create tasks for all API checks
        tasks = []
        
        # 1. Google Fact Check
        if self.api_keys['google']:
            tasks.append(('google', self.api_checkers.check_google_factcheck(claim)))
        
        # 2. AI Analysis
        if self.openai_client:
            tasks.append(('ai', self._check_with_ai_comprehensive(claim)))
        
        # 3. Economic data (FRED)
        if self._is_economic_claim(claim) and self.api_keys['fred']:
            tasks.append(('fred', self.api_checkers.check_fred_data(claim)))
        
        # 4. News sources
        if self.api_keys['news'] or self.api_keys['mediastack']:
            tasks.append(('news', self.api_checkers.check_news_sources(claim)))
        
        # 5. Wikipedia
        tasks.append(('wikipedia', self.api_checkers.check_wikipedia(claim)))
        
        # 6. Government data sources
        if self._is_government_data_claim(claim):
            if 'health' in claim.lower() or 'covid' in claim.lower():
                tasks.append(('cdc', self.api_checkers.check_cdc_data(claim)))
            if 'population' in claim.lower() or 'demographic' in claim.lower():
                tasks.append(('census', self.api_checkers.check_census_data(claim)))
            if 'climate' in claim.lower() or 'weather' in claim.lower():
                tasks.append(('noaa', self.api_checkers.check_noaa_data(claim)))
        
        # 7. Academic sources
        if self._is_academic_claim(claim):
            tasks.append(('academic', self.api_checkers.check_semantic_scholar(claim)))
        
        # Execute all tasks in parallel
        results = {}
        if tasks:
            task_names = [t[0] for t in tasks]
            task_coroutines = [t[1] for t in tasks]
            
            completed = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            for name, result in zip(task_names, completed):
                if isinstance(result, Exception):
                    logger.error(f"{name} check failed: {result}")
