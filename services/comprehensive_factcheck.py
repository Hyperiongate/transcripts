from collections import defaultdict
"""
Comprehensive Fact-Checking Service that uses ALL available APIs
Enhanced with aggressive AI analysis and reduced "needs context" results
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

# Enhanced verdict categories with better options for rhetoric and predictions
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
    'empty_rhetoric': {
        'label': 'Empty Rhetoric',
        'icon': '💨',
        'color': '#94a3b8',
        'score': None,
        'description': 'Vague promises or boasts with no substantive content'
    },
    'unsubstantiated_prediction': {
        'label': 'Unsubstantiated Prediction',
        'icon': '🔮',
        'color': '#a78bfa',
        'score': None,
        'description': 'Future claim with no evidence or plan provided'
    },
    'pattern_of_false_promises': {
        'label': 'Pattern of False Promises',
        'icon': '🔄',
        'color': '#f97316',
        'score': 10,
        'description': 'Speaker has history of similar unfulfilled claims'
    },
    'needs_context': {
        'label': 'Needs Context',
        'icon': '❓',
        'color': '#8b5cf6',
        'score': None,
        'description': 'Cannot verify without additional information'
    },
    'opinion': {
        'label': 'Opinion with Analysis',
        'icon': '💭',
        'color': '#6366f1',
        'score': None,
        'description': 'Subjective claim analyzed for factual elements'
    }
}

class ComprehensiveFactChecker:
    """Enhanced fact-checking that aggressively analyzes claims with AI"""
    
    def __init__(self, config):
        self.config = config
        self.current_speaker = None
        self.full_transcript = None  # Store full transcript for better context
        
        # Initialize all API keys
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
        
        # Initialize OpenAI with enhanced settings
        self.openai_client = None
        if self.api_keys['openai']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.api_keys['openai'])
                logger.info("OpenAI client initialized for aggressive fact-checking")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # Thread pool for parallel API calls
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Enhanced settings
        self.force_verdict = getattr(config, 'FORCE_VERDICT_ON_ALL_CLAIMS', True)
        self.confidence_threshold = getattr(config, 'CONFIDENCE_THRESHOLD_FOR_VERDICT', 50)
        self.enable_aggressive_checking = getattr(config, 'ENABLE_AGGRESSIVE_CHECKING', True)
    
    def check_claim_with_verdict(self, claim: str, context: Optional[Dict] = None) -> Dict:
        """Main entry point - check claim using ALL available resources"""
        try:
            # Clean claim
            claim = claim.strip()
            
            # Store transcript context for better analysis
            if context and context.get('transcript'):
                self.full_transcript = context['transcript']
            
            # Set current speaker for pattern analysis
            self.current_speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            
            # Check if this is trivial content
            if self._is_trivial_claim(claim):
                return None  # Skip trivial claims entirely
            
            # Enhanced context resolution with full transcript
            resolved_claim, context_info = self._resolve_claim_with_context(claim, context)
            if resolved_claim != claim:
                logger.info(f"Enhanced context resolution: {claim} -> {resolved_claim}")
                claim = resolved_claim
            
            # Check for empty rhetoric patterns first
            rhetoric_check = self._check_empty_rhetoric(claim)
            if rhetoric_check:
                return rhetoric_check
            
            # If we have OpenAI, use aggressive AI analysis first
            if self.openai_client and self.enable_aggressive_checking:
                ai_result = asyncio.run(self._aggressive_ai_analysis(claim, context))
                if ai_result and ai_result['verdict'] != 'needs_context':
                    # AI provided a definitive answer - use it
                    self.fact_history.add_check(claim, self.current_speaker, ai_result['verdict'], ai_result['explanation'])
                    return ai_result
            
            # Run comprehensive fact-checking for remaining cases
            result = asyncio.run(self._comprehensive_check(claim, self.current_speaker, None, False))
            
            # If still getting "needs context" and we have AI, force a verdict
            if result['verdict'] == 'needs_context' and self.openai_client and self.force_verdict:
                forced_result = asyncio.run(self._force_ai_verdict(claim, context))
                if forced_result:
                    result = forced_result
            
            # Add to history
            self.fact_history.add_check(claim, self.current_speaker, result['verdict'], result['explanation'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fact-check: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
    def _resolve_claim_with_context(self, claim: str, context: Optional[Dict]) -> Tuple[str, Dict]:
        """Enhanced context resolution using full transcript"""
        if not context or not context.get('transcript'):
            return claim, {}
        
        # Use context resolver with full transcript
        self.context_resolver.analyze_full_transcript(context['transcript'])
        resolved_claim, context_info = self.context_resolver.resolve_context(claim)
        
        # If claim is still vague, try to extract surrounding context
        if self.context_resolver.is_claim_too_vague(resolved_claim)['is_vague']:
            # Find this claim in the transcript and get surrounding sentences
            transcript = context['transcript']
            claim_pos = transcript.lower().find(claim.lower())
            if claim_pos >= 0:
                # Get 200 characters before and after for context
                start = max(0, claim_pos - 200)
                end = min(len(transcript), claim_pos + len(claim) + 200)
                surrounding_context = transcript[start:end]
                
                # Try to resolve with surrounding context
                if surrounding_context != claim:
                    enhanced_claim = f"{claim} [Context: {surrounding_context}]"
                    return enhanced_claim, {'surrounding_context': surrounding_context}
        
        return resolved_claim, context_info
    
    async def _aggressive_ai_analysis(self, claim: str, context: Optional[Dict]) -> Optional[Dict]:
        """Aggressive AI analysis that forces a verdict"""
        if not self.openai_client:
            return None
        
        try:
            # Build enhanced prompt with context
            context_info = ""
            if context and context.get('transcript'):
                # Find claim in transcript for surrounding context
                transcript = context['transcript']
                claim_pos = transcript.lower().find(claim.lower())
                if claim_pos >= 0:
                    start = max(0, claim_pos - 300)
                    end = min(len(transcript), claim_pos + len(claim) + 300)
                    surrounding = transcript[start:end]
                    context_info = f"\n\nSURROUNDING CONTEXT FROM TRANSCRIPT:\n{surrounding}"
            
            speaker_info = ""
            if self.current_speaker and self.current_speaker != 'Unknown':
                speaker_info = f"\n\nSPEAKER: {self.current_speaker}"
            
            # Enhanced prompt that demands a verdict
            prompt = f"""As an expert fact-checker, you MUST provide a definitive verdict on this claim. Do not say "needs context" unless absolutely impossible to analyze.

CLAIM TO FACT-CHECK: "{claim}"{speaker_info}{context_info}

Your task:
1. Identify what specific factual assertions this claim makes
2. Evaluate the truth of each factual component  
3. Consider if this is empty rhetoric, opinion, prediction, or factual claim
4. Provide a clear verdict from: TRUE, MOSTLY_TRUE, NEARLY_TRUE, EXAGGERATION, MISLEADING, MOSTLY_FALSE, FALSE, EMPTY_RHETORIC, UNSUBSTANTIATED_PREDICTION, OPINION
5. Explain your reasoning with specific details

IMPORTANT: 
- If you don't have perfect information, make your best assessment based on what you know
- Empty promises without specifics = EMPTY_RHETORIC
- Future claims without evidence/plans = UNSUBSTANTIATED_PREDICTION  
- Claims mixing fact and opinion = analyze the factual components
- Vague statements about "respect" or "greatness" = usually EMPTY_RHETORIC
- Only use "needs context" if genuinely impossible to analyze

Be decisive and thorough. What is your verdict?

VERDICT: [State your verdict clearly]
CONFIDENCE: [Rate 1-100]
EXPLANATION: [Detailed reasoning]"""

            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert fact-checker. You MUST provide definitive verdicts. Be decisive, thorough, and direct. Do not hedge or say 'needs context' unless truly impossible to analyze."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content
            
            # Enhanced verdict extraction
            verdict = self._extract_verdict_from_ai_response(result_text)
            confidence = self._extract_confidence_from_ai_response(result_text)
            explanation = self._extract_explanation_from_ai_response(result_text)
            
            logger.info(f"AI Analysis - Claim: {claim[:50]}... | Verdict: {verdict} | Confidence: {confidence}")
            
            return self._create_verdict(
                verdict,
                explanation,
                confidence=max(confidence, 60),  # Boost confidence for AI results
                sources=['Enhanced AI Analysis']
            )
            
        except Exception as e:
            logger.error(f"Aggressive AI analysis error: {e}")
            return None
    
    async def _force_ai_verdict(self, claim: str, context: Optional[Dict]) -> Optional[Dict]:
        """Force AI to provide a verdict when other methods fail"""
        if not self.openai_client:
            return None
            
        try:
            prompt = f"""This claim needs a verdict. You cannot respond with "needs context" or "uncertain". 

CLAIM: "{claim}"

Based on your training data, common knowledge, and logical analysis:

1. Is this a factual claim that can be evaluated? 
2. Is this empty political rhetoric without substance?
3. Is this an opinion with factual elements?
4. Is this a prediction about the future without supporting evidence?

You MUST choose one verdict:
- TRUE: Supported by evidence
- FALSE: Contradicted by evidence  
- MISLEADING: Partially true but creates false impression
- EXAGGERATION: Based on truth but overstated
- EMPTY_RHETORIC: Vague promises/boasts without substance
- OPINION: Subjective judgment that can't be proven true/false

What is your verdict and why? Be definitive."""

            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You must provide a definitive verdict. No hedging, no 'needs context', no uncertainty. Be decisive."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            verdict = self._extract_verdict_from_ai_response(result_text)
            
            # If AI still won't commit, default to opinion
            if verdict == 'needs_context':
                verdict = 'opinion'
                result_text += "\n\nNote: Classified as opinion when other analysis was inconclusive."
            
            return self._create_verdict(
                verdict,
                f"Forced Analysis: {result_text}",
                confidence=50,
                sources=['Forced AI Verdict']
            )
            
        except Exception as e:
            logger.error(f"Force AI verdict error: {e}")
            return None
    
    def _extract_verdict_from_ai_response(self, text: str) -> str:
        """Enhanced verdict extraction from AI response"""
        text_upper = text.upper()
        
        # Look for explicit verdict markers
        verdict_patterns = [
            r'VERDICT:\s*([A-Z_]+)',
            r'VERDICT\s*=\s*([A-Z_]+)',
            r'MY\s+VERDICT:\s*([A-Z_]+)',
            r'FINAL\s+VERDICT:\s*([A-Z_]+)'
        ]
        
        for pattern in verdict_patterns:
            match = re.search(pattern, text_upper)
            if match:
                verdict = match.group(1).lower()
                return self._normalize_verdict(verdict)
        
        # Look for verdict keywords in order of preference
        verdict_keywords = [
            ('EMPTY_RHETORIC', ['EMPTY RHETORIC', 'VAGUE PROMISES', 'NO SUBSTANCE', 'POLITICAL GRANDSTANDING']),
            ('UNSUBSTANTIATED_PREDICTION', ['UNSUBSTANTIATED PREDICTION', 'FUTURE CLAIM', 'NO EVIDENCE', 'NO PLAN']),
            ('FALSE', ['FALSE', 'INCORRECT', 'NOT TRUE', 'DEBUNKED', 'CONTRADICTED']),
            ('MOSTLY_FALSE', ['MOSTLY FALSE', 'LARGELY FALSE', 'SIGNIFICANT INACCURACIES']),
            ('MISLEADING', ['MISLEADING', 'DECEPTIVE', 'CREATES FALSE IMPRESSION']),
            ('EXAGGERATION', ['EXAGGERATION', 'OVERSTATED', 'HYPERBOLE']),
            ('TRUE', ['TRUE', 'ACCURATE', 'CORRECT', 'SUPPORTED BY EVIDENCE']),
            ('MOSTLY_TRUE', ['MOSTLY TRUE', 'LARGELY TRUE', 'GENERALLY ACCURATE']),
            ('NEARLY_TRUE', ['NEARLY TRUE', 'ALMOST TRUE', 'CLOSE TO ACCURATE']),
            ('OPINION', ['OPINION', 'SUBJECTIVE', 'VALUE JUDGMENT', 'PERSONAL VIEW'])
        ]
        
        for verdict_key, keywords in verdict_keywords:
            if any(keyword in text_upper for keyword in keywords):
                return verdict_key.lower()
        
        # Check for confidence indicators to infer verdict
        if any(phrase in text_upper for phrase in ['DEFINITELY FALSE', 'CLEARLY FALSE', 'OBVIOUSLY FALSE']):
            return 'false'
        elif any(phrase in text_upper for phrase in ['DEFINITELY TRUE', 'CLEARLY TRUE', 'OBVIOUSLY TRUE']):
            return 'true'
        elif any(phrase in text_upper for phrase in ['NO SUBSTANCE', 'JUST RHETORIC', 'EMPTY PROMISE']):
            return 'empty_rhetoric'
        
        # Default to opinion if we can't determine
        return 'opinion'
    
    def _extract_confidence_from_ai_response(self, text: str) -> int:
        """Enhanced confidence extraction"""
        # Look for explicit confidence ratings
        confidence_patterns = [
            r'CONFIDENCE:\s*(\d+)',
            r'CONFIDENCE\s*=\s*(\d+)',
            r'(\d+)%\s*CONFIDEN',
            r'CONFIDEN[CT]E?\s*:?\s*(\d+)'
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, text.upper())
            if match:
                return min(100, max(1, int(match.group(1))))
        
        # Infer confidence from language
        text_upper = text.upper()
        
        if any(phrase in text_upper for phrase in ['DEFINITELY', 'CERTAINLY', 'CLEARLY', 'OBVIOUSLY', 'WITHOUT DOUBT']):
            return 90
        elif any(phrase in text_upper for phrase in ['LIKELY', 'PROBABLY', 'APPEARS TO BE', 'SEEMS TO BE']):
            return 75
        elif any(phrase in text_upper for phrase in ['POSSIBLY', 'MIGHT BE', 'COULD BE', 'UNCLEAR']):
            return 55
        elif any(phrase in text_upper for phrase in ['EMPTY RHETORIC', 'NO SUBSTANCE', 'VAGUE PROMISE']):
            return 85  # High confidence for rhetoric detection
        
        return 70  # Default confidence
    
    def _extract_explanation_from_ai_response(self, text: str) -> str:
        """Extract explanation from AI response"""
        # Look for explanation section
        explanation_patterns = [
            r'EXPLANATION:\s*(.*?)(?:\n\n|\Z)',
            r'REASONING:\s*(.*?)(?:\n\n|\Z)',
            r'ANALYSIS:\s*(.*?)(?:\n\n|\Z)'
        ]
        
        for pattern in explanation_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no explicit explanation section, use the full response but clean it up
        explanation = text.strip()
        
        # Remove verdict line if it exists
        explanation = re.sub(r'VERDICT:\s*[A-Z_]+\s*', '', explanation, flags=re.IGNORECASE)
        explanation = re.sub(r'CONFIDENCE:\s*\d+\s*', '', explanation, flags=re.IGNORECASE)
        
        return explanation[:1000]  # Limit length
    
    def _is_trivial_claim(self, claim: str) -> bool:
        """Check if claim is trivial and should be skipped"""
        trivial_patterns = [
            r'^(hi|hello|hey|good\s+(morning|afternoon|evening|night))',
            r'^(thank\s+you|thanks)',
            r'^(welcome|you\'re welcome)',
            r'^(please|excuse me)',
            r'^(um+|uh+|ah+|oh+|hmm+)',
            r'^(yes|no|yeah|nope|yep|okay|ok|alright)',
            r'^(i mean|you know|like|so|well|anyway)',
            r'^\s*\[.*?\]\s*$',  # Stage directions
            r'^(applause|laughter|music)',
            r'^(ladies and gentlemen|my fellow americans|folks)',  # Common intros
        ]
        
        claim_lower = claim.lower().strip()
        for pattern in trivial_patterns:
            if re.match(pattern, claim_lower):
                return True
        
        # Also skip if under 10 characters or 3 words
        if len(claim) < 10 or len(claim.split()) < 3:
            return True
            
        return False
    
    def _check_empty_rhetoric(self, claim: str) -> Optional[Dict]:
        """Enhanced empty rhetoric detection"""
        claim_lower = claim.lower()
        
        # Expanded boast patterns
        boast_patterns = [
            (r'will\s+(be\s+)?(respected|great|best|wonderful|amazing|fantastic|incredible)', 'boast'),
            (r'from\s+this\s+day\s+forward', 'dramatic_promise'),
            (r'will\s+(flourish|prosper|succeed|win|triumph)', 'vague_promise'),
            (r'(everyone|everybody|the\s+whole\s+world)\s+will', 'sweeping_claim'),
            (r'like\s+never\s+before', 'unprecedented_claim'),
            (r'the\s+(greatest|best|most)\s+.*\s+(ever|in\s+history)', 'superlative_claim'),
            (r'make\s+.*\s+great\s+again', 'vague_promise'),
            (r'incredible|tremendous|phenomenal|unbelievable|fantastic', 'hyperbole'),
            (r'will\s+be\s+so\s+(proud|happy|successful)', 'emotional_appeal'),
            (r'nobody\s+has\s+ever\s+seen', 'unprecedented_boast'),
        ]
        
        matched_patterns = []
        for pattern, pattern_type in boast_patterns:
            if re.search(pattern, claim_lower):
                matched_patterns.append(pattern_type)
        
        if matched_patterns:
            # Check for substantive content
            substantive_indicators = [
                'because', 'by', 'through', 'plan', 'policy', 'legislation', 
                'implement', 'invest', 'reform', 'billion', 'million', 'percent',
                'budget', 'funding', 'timeline', 'deadline', 'specific', 'executive order',
                'congress will', 'senate will', 'house will', 'department of'
            ]
            
            has_substance = any(indicator in claim_lower for indicator in substantive_indicators)
            
            if not has_substance:
                confidence = 85 + min(15, len(matched_patterns) * 3)  # Higher confidence for more patterns
                
                return self._create_verdict(
                    'empty_rhetoric',
                    f"This statement exhibits classic empty rhetoric patterns: {', '.join(matched_patterns)}. It makes grand promises or boasts without providing specific policies, timelines, budgets, or implementation plans. Such statements are designed to evoke emotional responses rather than convey substantive policy commitments. Without concrete details about HOW these outcomes will be achieved, this remains aspirational language rather than factual claims that can be verified.",
                    confidence=confidence
                )
        
        return None
    
    async def _comprehensive_check(self, claim: str, speaker: str, historical: Optional[Dict], is_opinion: bool) -> Dict:
        """Run comprehensive fact-checking with all available sources"""
        
        # Build task list based on available APIs
        tasks = []
        
        # 1. Google Fact Check API
        if self.api_keys['google']:
            tasks.append(('google', self.api_checkers.check_google_factcheck(claim)))
        
        # 2. Enhanced AI Analysis if we haven't used it yet
        if self.openai_client:
            tasks.append(('ai_comprehensive', self._ai_comprehensive_analysis(claim, is_opinion)))
        
        # 3. Economic data checks
        if self._is_economic_claim(claim) and self.api_keys['fred']:
            tasks.append(('fred', self.api_checkers.check_fred_data(claim)))
        
        # 4. News source verification
        if self.api_keys['news'] or self.api_keys['mediastack']:
            tasks.append(('news', self.api_checkers.check_news_sources(claim)))
        
        # 5. Wikipedia cross-reference
        tasks.append(('wikipedia', self.api_checkers.check_wikipedia(claim)))
        
        # Execute all tasks
        results = {}
        if tasks:
            task_names = [t[0] for t in tasks]
            task_coroutines = [t[1] for t in tasks]
            
            completed = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            for name, result in zip(task_names, completed):
                if isinstance(result, Exception):
                    logger.error(f"{name} check failed: {result}")
                    results[name] = {'found': False}
                else:
                    results[name] = result
        
        # Aggregate results with enhanced logic
        return self._aggregate_results_enhanced(claim, results, speaker, historical)
    
    async def _ai_comprehensive_analysis(self, claim: str, is_opinion: bool) -> Dict:
        """Comprehensive AI analysis for aggregation"""
        if not self.openai_client:
            return {'found': False}
        
        try:
            analysis_type = "opinion with factual elements" if is_opinion else "factual claim"
            
            prompt = f"""Provide a comprehensive analysis of this {analysis_type}:

CLAIM: "{claim}"

Your analysis should cover:
1. What specific facts or assumptions are embedded in this statement?
2. What evidence supports these elements?
3. What evidence contradicts these elements?  
4. Is this verifiable, opinion-based, or empty rhetoric?
5. What's the appropriate verdict?

Possible verdicts: TRUE, MOSTLY_TRUE, NEARLY_TRUE, MISLEADING, EXAGGERATION, MOSTLY_FALSE, FALSE, EMPTY_RHETORIC, UNSUBSTANTIATED_PREDICTION, OPINION

Provide your verdict and detailed reasoning."""

            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Provide thorough, balanced analysis. Be specific about evidence and reasoning."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content
            verdict = self._extract_verdict_from_ai_response(result_text)
            confidence = self._extract_confidence_from_ai_response(result_text)
            
            return {
                'found': True,
                'verdict': verdict,
                'explanation': result_text,
                'confidence': confidence,
                'source': 'Comprehensive AI Analysis',
                'weight': 0.7
            }
            
        except Exception as e:
            logger.error(f"AI comprehensive analysis error: {e}")
            return {'found': False}
    
    def _aggregate_results_enhanced(self, claim: str, results: Dict, speaker: str, historical: Optional[Dict]) -> Dict:
        """Enhanced result aggregation that avoids 'needs context'"""
        
        # Collect all findings
        verdicts = []
        explanations = []
        sources_used = []
        
        for source, result in results.items():
            if result.get('found') and result.get('verdict') != 'needs_context':
                verdicts.append({
                    'verdict': result.get('verdict'),
                    'weight': result.get('weight', 0.5),
                    'confidence': result.get('confidence', 60),
                    'source': source
                })
                
                if result.get('explanation'):
                    explanations.append(f"{source.upper()}: {result['explanation']}")
                
                sources_used.append(result.get('source', source))
        
        # If we have any verdict, use weighted analysis
        if verdicts:
            return self._calculate_final_verdict(verdicts, explanations, sources_used, claim, speaker)
        
        # If no definitive verdicts but we have OpenAI, force analysis
        if self.openai_client and self.force_verdict:
            forced_result = asyncio.run(self._force_ai_verdict(claim, None))
            if forced_result:
                return forced_result
        
        # Enhanced pattern matching as last resort
        pattern_result = self._enhanced_pattern_matching(claim)
        if pattern_result:
            return pattern_result
        
        # Final fallback - classify based on content type
        return self._classify_by_content_type(claim)
    
    def _calculate_final_verdict(self, verdicts: List[Dict], explanations: List[str], 
                                sources: List[str], claim: str, speaker: str) -> Dict:
        """Calculate final verdict using weighted analysis"""
        
        # Verdict scoring system
        verdict_scores = {
            'true': 1.0,
            'mostly_true': 0.8,
            'nearly_true': 0.7,
            'exaggeration': 0.5,
            'opinion': 0.5,
            'misleading': 0.3,
            'mostly_false': 0.2,
            'false': 0.0,
            'empty_rhetoric': 0.0,
            'unsubstantiated_prediction': 0.1,
            'pattern_of_false_promises': 0.1
        }
        
        # Calculate weighted score
        total_score = 0
        total_weight = 0
        total_confidence = 0
        
        for v in verdicts:
            verdict_key = self._normalize_verdict(v['verdict'])
            if verdict_key in verdict_scores:
                weight = v['weight']
                score = verdict_scores[verdict_key]
                confidence = v['confidence']
                
                total_score += score * weight
                total_weight += weight
                total_confidence += confidence * weight
        
        if total_weight == 0:
            return self._classify_by_content_type(claim)
        
        # Determine final verdict
        avg_score = total_score / total_weight
        avg_confidence = int(total_confidence / total_weight)
        
        if avg_score >= 0.85:
            final_verdict = 'true'
        elif avg_score >= 0.70:
            final_verdict = 'mostly_true'
        elif avg_score >= 0.60:
            final_verdict = 'nearly_true'
        elif avg_score >= 0.45:
            final_verdict = 'exaggeration'
        elif avg_score >= 0.25:
            final_verdict = 'misleading'
        elif avg_score >= 0.15:
            final_verdict = 'mostly_false'
        else:
            final_verdict = 'false'
        
        # Build explanation
        explanation_parts = []
        if len(explanations) > 1:
            explanation_parts.append("ANALYSIS FROM MULTIPLE SOURCES:")
        explanation_parts.extend(explanations)
        
        # Add summary
        explanation_parts.append(f"\n\nSUMMARY: Based on analysis from {len(verdicts)} source(s), this claim is classified as {final_verdict.replace('_', ' ').title()}.")
        
        return self._create_verdict(
            final_verdict,
            '\n\n'.join(explanation_parts),
            confidence=max(avg_confidence, 60),
            sources=sources
        )
    
    def _enhanced_pattern_matching(self, claim: str) -> Optional[Dict]:
        """Enhanced pattern matching for common claim types"""
        claim_lower = claim.lower()
        
        # Government/administrative claims
        if re.search(r'\b(government|administration|president|congress)\b', claim_lower):
            if re.search(r'\b(crisis|disaster|catastrophic|stumbling|cannot manage)\b', claim_lower):
                return self._create_verdict(
                    'opinion',
                    'This appears to be a political opinion about government performance. Such characterizations are subjective and depend on which metrics and priorities different observers emphasize. Objective assessment would require specific examples and measurable criteria.',
                    confidence=70
                )
        
        # Superlative claims (best/worst ever)
        if re.search(r'\b(best|worst|greatest|most|least).*\b(ever|in history|of all time)\b', claim_lower):
            return self._create_verdict(
                'exaggeration',
                'Claims using superlatives like "best ever" or "worst in history" are typically exaggerations. Such absolute statements rarely account for the full scope of historical comparison and often reflect political rhetoric rather than objective analysis.',
                confidence=75
            )
        
        # Future predictions without specifics
        if re.search(r'\b(will be|going to be|guarantee).*\b(great|successful|respected|amazing)\b', claim_lower):
            return self._create_verdict(
                'unsubstantiated_prediction',
                'This is a prediction about future outcomes without specific evidence, plans, or measurable criteria. Such promises are common in political rhetoric but cannot be verified until concrete policies are implemented and outcomes measured.',
                confidence=80
            )
        
        return None
    
    def _classify_by_content_type(self, claim: str) -> Dict:
        """Classify claim by content type as final fallback"""
        claim_lower = claim.lower()
        
        # Opinion indicators
        opinion_words = ['terrible', 'great', 'amazing', 'horrible', 'disaster', 'wonderful', 'incredible', 'fantastic']
        if any(word in claim_lower for word in opinion_words):
            return self._create_verdict(
                'opinion',
                'This statement contains subjective language that expresses an opinion or value judgment. While it may reference factual situations, the characterization reflects the speaker\'s perspective rather than objective, verifiable facts.',
                confidence=65
            )
        
        # Check for factual elements that could be verified
        factual_indicators = ['percent', '%', 'million', 'billion', 'increased', 'decreased', 'data', 'statistics', 'report']
        if any(indicator in claim_lower for indicator in factual_indicators):
            return self._create_verdict(
                'misleading',
                'This claim appears to contain factual elements that could potentially be verified, but without access to the specific data sources referenced, we cannot confirm its accuracy. The statement may be mixing factual information with interpretation.',
                confidence=55
            )
        
        # Default to opinion for unclassifiable claims
        return self._create_verdict(
            'opinion',
            'This statement does not appear to make specific, verifiable factual claims. It seems to express a viewpoint or characterization that is subjective in nature.',
            confidence=50
        )
    
    def _is_economic_claim(self, claim: str) -> bool:
        """Check if claim relates to economic data"""
        economic_keywords = [
            'unemployment', 'inflation', 'gdp', 'economy', 'jobs',
            'wage', 'income', 'deficit', 'debt', 'budget', 'trade',
            'tariff', 'tax', 'revenue', 'spending', 'growth',
            'recession', 'stock market', 'dow jones', 'nasdaq'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in economic_keywords)
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict strings"""
        if not verdict:
            return 'opinion'
            
        verdict = verdict.lower().strip().replace(' ', '_')
        
        # Direct mappings
        verdict_map = {
            'true': 'true',
            'mostly_true': 'mostly_true', 
            'nearly_true': 'nearly_true',
            'exaggeration': 'exaggeration',
            'misleading': 'misleading',
            'mostly_false': 'mostly_false',
            'false': 'false',
            'empty_rhetoric': 'empty_rhetoric',
            'unsubstantiated_prediction': 'unsubstantiated_prediction',
            'pattern_of_false_promises': 'pattern_of_false_promises',
            'opinion': 'opinion',
            'mixed': 'exaggeration'  # Treat mixed as exaggeration
        }
        
        return verdict_map.get(verdict, 'opinion')
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 60, sources: List[str] = None) -> Dict:
        """Create standardized verdict"""
        return {
            'verdict': verdict,
            'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
            'explanation': explanation,
            'confidence': max(confidence, 50),  # Minimum confidence of 50
            'sources': sources or [],
            'timestamp': datetime.now().isoformat()
        }

# Compatibility wrapper
class FactChecker(ComprehensiveFactChecker):
    """Wrapper for compatibility"""
    pass
