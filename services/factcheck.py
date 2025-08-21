"""
Enhanced Fact-Checking Service with AI Integration
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

# Get logger but don't use it at module level
logger = logging.getLogger(__name__)

# Enhanced verdict categories with nuanced options
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
    'intentionally_deceptive': {
        'label': 'Intentionally Deceptive',
        'icon': '🚨',
        'color': '#b91c1c',
        'score': 0,
        'description': 'Deliberately false or manipulative'
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

class FactChecker:
    """Enhanced fact-checking service with AI integration"""
    
    def __init__(self, config):
        self.config = config
        self.google_api_key = getattr(config, 'GOOGLE_FACTCHECK_API_KEY', None)
        self.openai_api_key = getattr(config, 'OPENAI_API_KEY', None)
        self.fred_api_key = getattr(config, 'FRED_API_KEY', None)
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Knowledge base for common facts
        self.knowledge_base = {
            'debate_facts': {
                'trump_harris_debate_2024': {
                    'date': 'September 10, 2024',
                    'occurred': True,
                    'context': 'Presidential debate between Donald Trump and Kamala Harris'
                }
            },
            'political_facts': {
                'trump_wars': {
                    'new_wars_started': 0,
                    'context': 'No new wars during Trump presidency 2017-2021'
                }
            }
        }
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Check a claim and return enhanced verdict with explanation"""
        try:
            # First, check if it's an opinion
            if self._is_opinion(claim):
                return {
                    'verdict': 'opinion',
                    'verdict_details': VERDICT_CATEGORIES['opinion'],
                    'explanation': 'This is a subjective opinion rather than a verifiable fact.',
                    'confidence': 95,
                    'sources': [],
                    'ai_analysis_used': False
                }
            
            # Try AI analysis first if available
            if self.openai_client and self.config.ENABLE_AI_FACT_CHECKING:
                ai_result = self._check_with_ai(claim, context)
                if ai_result:
                    return ai_result
            
            # Check Google Fact Check API
            if self.google_api_key:
                google_result = self._check_google_fact_check(claim)
                if google_result:
                    return google_result
            
            # Check internal knowledge base
            kb_result = self._check_knowledge_base(claim)
            if kb_result:
                return kb_result
            
            # Default to needs context
            return {
                'verdict': 'needs_context',
                'verdict_details': VERDICT_CATEGORIES['needs_context'],
                'explanation': 'Unable to verify this claim with available sources.',
                'confidence': 0,
                'sources': [],
                'ai_analysis_used': False
            }
            
        except Exception as e:
            logger.error(f"Error checking claim: {e}")
            return {
                'verdict': 'needs_context',
                'verdict_details': VERDICT_CATEGORIES['needs_context'],
                'explanation': f'Error during fact-checking: {str(e)}',
                'confidence': 0,
                'sources': [],
                'ai_analysis_used': False
            }
    
    def _is_opinion(self, claim: str) -> bool:
        """Check if a claim is an opinion rather than a fact"""
        opinion_indicators = [
            r'\b(i think|i believe|i feel|in my opinion|seems|appears)\b',
            r'\b(should|ought to|must|need to)\b',
            r'\b(best|worst|greatest|terrible|amazing|horrible)\b',
            r'\b(beautiful|ugly|good|bad|nice|awful)\b'
        ]
        
        claim_lower = claim.lower()
        for pattern in opinion_indicators:
            if re.search(pattern, claim_lower):
                return True
        
        return False
    
    def _check_with_ai(self, claim: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """Use AI to analyze claim with enhanced verdict system"""
        try:
            # Build context-aware prompt
            context_info = ""
            if context:
                if context.get('speech_date'):
                    context_info += f"Speech date: {context['speech_date']}\n"
                if context.get('speakers'):
                    context_info += f"Speakers: {', '.join(context['speakers'])}\n"
            
            prompt = f"""Analyze this claim for factual accuracy. Determine the most appropriate verdict and explain why.

Verdicts to choose from:
- TRUE: Completely accurate
- MOSTLY_TRUE: Accurate with minor imprecision
- NEARLY_TRUE: Largely accurate but missing context
- EXAGGERATION: Based on truth but overstated
- MISLEADING: Contains truth but creates false impression
- MOSTLY_FALSE: Significant inaccuracies
- FALSE: Demonstrably incorrect
- INTENTIONALLY_DECEPTIVE: Deliberately false or manipulative
- NEEDS_CONTEXT: Cannot verify without more information
- OPINION: Subjective statement, not factual

{context_info}
Claim: "{claim}"

Analyze for:
1. Is this a fact or opinion?
2. If fact, is it accurate?
3. Is there intent to deceive?
4. What context is missing?

Format: VERDICT|CONFIDENCE|EXPLANATION|INTENT"""

            response = self.openai_client.chat.completions.create(
                model=getattr(self.config, 'OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": "You are a professional fact-checker. Be precise and thorough."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            parts = result.split('|')
            
            if len(parts) >= 3:
                verdict = self._normalize_verdict(parts[0].strip())
                confidence = int(parts[1].strip()) if parts[1].strip().isdigit() else 70
                explanation = parts[2].strip()
                intent = parts[3].strip() if len(parts) > 3 else 'unclear'
                
                # Adjust verdict based on intent
                if intent.lower() in ['deceptive', 'intentional', 'deliberate'] and verdict in ['false', 'mostly_false', 'misleading']:
                    verdict = 'intentionally_deceptive'
                
                return {
                    'verdict': verdict,
                    'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
                    'explanation': explanation,
                    'confidence': confidence,
                    'sources': ['AI Analysis (GPT-4)' if 'gpt-4' in str(self.config.OPENAI_MODEL) else 'AI Analysis'],
                    'ai_analysis_used': True,
                    'intent_analysis': intent
                }
                
        except Exception as e:
            logger.error(f"AI fact-checking error: {e}")
        
        return None
    
    def _check_google_fact_check(self, claim: str) -> Optional[Dict]:
        """Check claim using Google Fact Check API"""
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim[:200],  # API limit
                'pageSize': 5
            }
            
            response = requests.get(url, params=params, timeout=getattr(self.config, 'API_TIMEOUT', 5))
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Analyze the first relevant claim
                    for claim_review in data['claims']:
                        if 'claimReview' in claim_review:
                            for review in claim_review['claimReview']:
                                rating = review.get('textualRating', '').lower()
                                verdict = self._map_google_rating_to_verdict(rating)
                                
                                return {
                                    'verdict': verdict,
                                    'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
                                    'explanation': review.get('title', 'Fact check available'),
                                    'confidence': 85,
                                    'sources': [review.get('publisher', {}).get('name', 'Fact Checker')],
                                    'ai_analysis_used': False,
                                    'url': review.get('url')
                                }
                                
        except Exception as e:
            logger.error(f"Google Fact Check API error: {e}")
        
        return None
    
    def _check_knowledge_base(self, claim: str) -> Optional[Dict]:
        """Check against internal knowledge base"""
        claim_lower = claim.lower()
        
        # Check for Trump-Harris debate
        if 'trump' in claim_lower and 'harris' in claim_lower and 'debate' in claim_lower:
            if 'never' in claim_lower or 'didn\'t' in claim_lower or 'did not' in claim_lower:
                return {
                    'verdict': 'false',
                    'verdict_details': VERDICT_CATEGORIES['false'],
                    'explanation': 'Trump and Harris did have a presidential debate on September 10, 2024.',
                    'confidence': 95,
                    'sources': ['Historical Record'],
                    'ai_analysis_used': False
                }
        
        # Check for Trump wars claim
        if 'trump' in claim_lower and ('war' in claim_lower or 'wars' in claim_lower) and ('start' in claim_lower or 'new' in claim_lower):
            if 'didn\'t' in claim_lower or 'did not' in claim_lower or 'no new' in claim_lower:
                return {
                    'verdict': 'true',
                    'verdict_details': VERDICT_CATEGORIES['true'],
                    'explanation': 'Trump did not start any new wars during his presidency (2017-2021).',
                    'confidence': 90,
                    'sources': ['Historical Record'],
                    'ai_analysis_used': False
                }
        
        return None
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict string to standard format"""
        verdict_lower = verdict.lower().strip()
        
        # Direct mappings
        mappings = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'nearly true': 'nearly_true',
            'exaggeration': 'exaggeration',
            'exaggerated': 'exaggeration',
            'misleading': 'misleading',
            'mostly false': 'mostly_false',
            'false': 'false',
            'deceptive': 'intentionally_deceptive',
            'intentionally deceptive': 'intentionally_deceptive',
            'needs context': 'needs_context',
            'opinion': 'opinion',
            'unverified': 'needs_context'
        }
        
        for key, value in mappings.items():
            if key in verdict_lower:
                return value
        
        return 'needs_context'
    
    def _map_google_rating_to_verdict(self, rating: str) -> str:
        """Map Google Fact Check ratings to our verdict system"""
        rating_lower = rating.lower()
        
        mappings = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'half true': 'nearly_true',
            'mostly false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'misleading': 'misleading',
            'lacks context': 'needs_context',
            'unproven': 'needs_context',
            'exaggerated': 'exaggeration'
        }
        
        for key, value in mappings.items():
            if key in rating_lower:
                return value
        
        return 'needs_context'
    
    def get_speaker_context(self, speaker_name: str) -> Dict[str, Any]:
        """Get comprehensive context about a speaker"""
        # This would integrate with your speaker database
        # For now, returning a simple structure
        return {
            'criminal_record': None,
            'fraud_history': None,
            'fact_check_history': {
                'total_claims': 0,
                'false_claims': 0,
                'accuracy_rate': 0
            }
        }
    
    def check_claim_comprehensive(self, claim: str, context: Dict[str, Any]) -> Dict:
        """Comprehensive fact-checking using all available methods"""
        return self.check_claim_with_verdict(claim, context)
    
    def generate_summary(self, fact_checks: List[Dict]) -> str:
        """Generate a summary of fact check results"""
        if not fact_checks:
            return "No claims were fact-checked."
        
        total = len(fact_checks)
        verdict_counts = {}
        
        for fc in fact_checks:
            verdict = fc.get('verdict', 'needs_context')
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        summary = f"Analyzed {total} claims:\n"
        for verdict, count in verdict_counts.items():
            verdict_info = VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context'])
            summary += f"- {verdict_info['label']}: {count}\n"
        
        return summary
