from collections import defaultdict
"""
Comprehensive Fact-Checking Service that uses ALL available APIs
Enhanced with empty rhetoric detection and thorough opinion analysis
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
    """Enhanced fact-checking that actually uses all available services"""
    
    def __init__(self, config):
        self.config = config
        self.current_speaker = None  # Track current speaker for pattern analysis
        
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
            
            # Set current speaker for pattern analysis
            self.current_speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            
            # Check if this is trivial content
            if self._is_trivial_claim(claim):
                return None  # Skip trivial claims entirely
            
            # Check if too short but not trivial
            if len(claim.split()) < 4:
                return self._create_verdict('needs_context', 'Statement too short to analyze meaningfully')
            
            # First check for empty rhetoric patterns
            rhetoric_check = self._check_empty_rhetoric(claim)
            if rhetoric_check:
                return rhetoric_check
            
            # Resolve context (pronouns, references)
            if context and context.get('transcript'):
                self.context_resolver.analyze_full_transcript(context['transcript'])
            
            resolved_claim, context_info = self.context_resolver.resolve_context(claim)
            if resolved_claim != claim:
                logger.info(f"Resolved claim: {claim} -> {resolved_claim}")
                claim = resolved_claim
            
            # Check if claim is too vague
            vagueness = self.context_resolver.is_claim_too_vague(claim)
            if vagueness['is_vague'] and not self._contains_implicit_facts(claim):
                return self._create_verdict('needs_context', vagueness['reason'])
            
            # Check historical patterns
            speaker = context.get('speaker', 'Unknown') if context else 'Unknown'
            historical = self.fact_history.get_historical_context(claim, speaker)
            
            # Even if it's an opinion, analyze it for factual components
            is_opinion = self._is_opinion_with_facts(claim)
            
            # Run comprehensive fact-checking
            result = asyncio.run(self._comprehensive_check(claim, speaker, historical, is_opinion))
            
            # Add to history
            self.fact_history.add_check(claim, speaker, result['verdict'], result['explanation'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fact-check: {e}")
            return self._create_verdict('needs_context', f'Error during fact-checking: {str(e)}')
    
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
        """Check for empty rhetoric, boasts, and unsubstantiated predictions"""
        claim_lower = claim.lower()
        
        # Check for empty boastful rhetoric
        boast_patterns = [
            (r'will\s+(be\s+)?(respected|great|best|wonderful|amazing|fantastic)', 'boast'),
            (r'from\s+this\s+day\s+forward', 'dramatic_promise'),
            (r'will\s+(flourish|prosper|succeed|win)', 'vague_promise'),
            (r'(everyone|everybody|the\s+whole\s+world)\s+will', 'sweeping_claim'),
            (r'like\s+never\s+before', 'unprecedented_claim'),
            (r'the\s+(greatest|best|most)\s+.*\s+(ever|in\s+history)', 'superlative_claim'),
            (r'make\s+.*\s+great\s+again', 'vague_promise'),
            (r'incredible|tremendous|phenomenal|unbelievable', 'hyperbole'),
        ]
        
        matched_patterns = []
        for pattern, pattern_type in boast_patterns:
            if re.search(pattern, claim_lower):
                matched_patterns.append(pattern_type)
        
        if matched_patterns:
            # Check if there's any substantive content
            substantive_indicators = ['because', 'by', 'through', 'plan', 'policy', 'legislation', 
                                    'implement', 'invest', 'reform', 'billion', 'million', 'percent']
            
            has_substance = any(indicator in claim_lower for indicator in substantive_indicators)
            
            if not has_substance:
                # Check speaker history
                speaker_history = ""
                if hasattr(self, 'fact_history') and self.current_speaker != 'Unknown':
                    similar_claims = self.fact_history.get_similar_empty_promises(self.current_speaker)
                    if similar_claims:
                        speaker_history = f"\n\nPATTERN DETECTED: {self.current_speaker} has made {len(similar_claims)} similar vague promises previously without providing specific plans or following through."
                
                return self._create_verdict(
                    'empty_rhetoric',
                    f"This is empty rhetoric typical of political grandstanding. The statement contains {', '.join(matched_patterns)} but provides no specific plans, policies, timelines, or measurable goals. Without concrete details about HOW these outcomes will be achieved, this is merely aspirational language designed to evoke emotion rather than convey factual information.{speaker_history}",
                    confidence=90
                )
        
        # Check for unsubstantiated future predictions
        future_patterns = [
            r'will\s+(always|definitely|certainly|absolutely)',
            r'(going\s+to|gonna)\s+(be|make|have|become)\s+.*\s+(great|best|respected)',
            r'(america|country|nation)\s+will\s+be\s+.*\s+again',
            r'guarantee|promise|ensure|assure',
        ]
        
        for pattern in future_patterns:
            if re.search(pattern, claim_lower) and not has_substance:
                return self._create_verdict(
                    'unsubstantiated_prediction',
                    'This is an unsubstantiated prediction about future events. No evidence, specific policies, implementation plans, or measurable metrics are provided to support this claim. Sweeping promises about future outcomes should be evaluated based on concrete proposals and track records rather than rhetoric alone.',
                    confidence=85
                )
        
        return None
    
    def _is_opinion_with_facts(self, claim: str) -> bool:
        """Check if claim is opinion but contains factual elements to analyze"""
        opinion_indicators = [
            'cannot manage', 'stumbling into', 'catastrophic',
            'terrible', 'great', 'amazing', 'horrible', 'disaster',
            'best', 'worst', 'failure', 'success', 'incompetent',
            'brilliant', 'stupid', 'corrupt', 'honest'
        ]
        
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in opinion_indicators)
    
    def _contains_implicit_facts(self, claim: str) -> bool:
        """Check if claim contains implicit factual assertions"""
        factual_indicators = [
            'government', 'crisis', 'policy', 'economy', 'border',
            'war', 'conflict', 'spending', 'deficit', 'crime',
            'immigration', 'healthcare', 'education', 'infrastructure',
            'unemployment', 'inflation', 'trade', 'manufacturing'
        ]
        
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in factual_indicators)
    
    async def _comprehensive_check(self, claim: str, speaker: str, historical: Optional[Dict], is_opinion: bool) -> Dict:
        """Run all fact-checking methods in parallel"""
        
        # If it's an opinion, first extract factual components
        if is_opinion:
            factual_components = await self._extract_factual_components(claim)
            if factual_components:
                return await self._analyze_opinion_with_facts(claim, factual_components, speaker, historical)
        
        # Otherwise, proceed with normal fact-checking
        tasks = []
        
        # 1. Google Fact Check
        if self.api_keys['google']:
            tasks.append(('google', self.api_checkers.check_google_factcheck(claim)))
        
        # 2. AI Analysis - Enhanced for opinions
        if self.openai_client:
            tasks.append(('ai', self._check_with_ai_comprehensive(claim, is_opinion)))
        
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
                    results[name] = {'found': False}
                else:
                    results[name] = result
        
        # Aggregate results
        return self._aggregate_results(claim, results, speaker, historical)
    
    async def _extract_factual_components(self, claim: str) -> List[Dict]:
        """Extract factual components from an opinion statement"""
        if not self.openai_client:
            return []
        
        try:
            prompt = f"""Analyze this statement and extract any factual claims or assumptions that can be verified:

Statement: "{claim}"

Identify:
1. What specific events, policies, or situations might this refer to?
2. What factual claims are implicit in this statement?
3. What data or evidence would be needed to evaluate this fairly?
4. Are there any measurable metrics implied?

Format your response as a list of specific, verifiable claims. If the statement is pure rhetoric with no verifiable content, say so."""

            response = self.openai_client.chat.completions.create(
                model='gpt-4' if hasattr(self.config, 'USE_GPT4') and self.config.USE_GPT4 else 'gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "Extract factual components from opinions for verification. Be specific and precise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Parse the response to extract factual claims
            content = response.choices[0].message.content
            
            # Check if AI says it's pure rhetoric
            if 'pure rhetoric' in content.lower() or 'no verifiable content' in content.lower():
                return []
            
            factual_claims = []
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('Identify:', 'Format:', '1.', '2.', '3.', '4.')):
                    if len(line) > 20:  # Skip very short lines
                        factual_claims.append({
                            'claim': line.strip('- •'),
                            'original': claim
                        })
            
            return factual_claims[:5]  # Limit to 5 most relevant
            
        except Exception as e:
            logger.error(f"Error extracting factual components: {e}")
            return []
    
    async def _analyze_opinion_with_facts(self, original_claim: str, factual_components: List[Dict], 
                                         speaker: str, historical: Optional[Dict]) -> Dict:
        """Analyze an opinion by checking its factual components"""
        
        # Special handling for known patterns of empty promises
        if historical and historical.get('pattern') == 'false_promises':
            similar_claims = historical.get('similar_claims', [])
            if len(similar_claims) > 3:
                return self._create_verdict(
                    'pattern_of_false_promises',
                    f'{speaker} has made {len(similar_claims)} similar sweeping promises in the past without following through. Examples include: {", ".join(similar_claims[:3])}... This appears to be another instance of empty rhetoric rather than a substantive policy commitment. Past promises have not been accompanied by specific legislation, executive orders, or measurable outcomes.',
                    confidence=90
                )
        
        # Check each factual component
        component_results = []
        for component in factual_components:
            result = await self._comprehensive_check(component['claim'], speaker, historical, False)
            component_results.append({
                'claim': component['claim'],
                'result': result
            })
        
        # Build comprehensive explanation
        explanation_parts = [
            f"This statement contains both opinion and factual implications. Here's our analysis:\n"
        ]
        
        # Add analysis of each component
        for i, comp_result in enumerate(component_results, 1):
            verdict = comp_result['result']['verdict']
            exp = comp_result['result']['explanation']
            explanation_parts.append(f"\n{i}. Regarding '{comp_result['claim']}':")
            explanation_parts.append(f"   Verdict: {verdict}")
            explanation_parts.append(f"   {exp}")
        
        # Add context and balance
        explanation_parts.append("\n\nCONTEXT AND BALANCE:")
        explanation_parts.append(self._get_balanced_context(original_claim))
        
        # Add speaker pattern analysis if available
        if speaker != 'Unknown':
            pattern_analysis = self._analyze_speaker_patterns(speaker, original_claim)
            if pattern_analysis:
                explanation_parts.append(f"\n\nSPEAKER PATTERN ANALYSIS:\n{pattern_analysis}")
        
        # Determine overall verdict based on factual components
        verdicts = [cr['result']['verdict'] for cr in component_results]
        if all(v in ['true', 'mostly_true'] for v in verdicts):
            final_verdict = 'opinion'
            explanation_parts.append("\n\nCONCLUSION: While this is an opinion, the underlying factual premises are largely supported by evidence.")
        elif all(v in ['false', 'mostly_false'] for v in verdicts):
            final_verdict = 'misleading'
            explanation_parts.append("\n\nCONCLUSION: This opinion is based on factual premises that are not supported by evidence.")
        elif any(v in ['empty_rhetoric', 'unsubstantiated_prediction'] for v in verdicts):
            final_verdict = 'empty_rhetoric'
            explanation_parts.append("\n\nCONCLUSION: This statement lacks substantive content and appears to be political rhetoric.")
        else:
            final_verdict = 'opinion'
            explanation_parts.append("\n\nCONCLUSION: This opinion contains mixed factual premises - some supported by evidence, others not.")
        
        return self._create_verdict(
            final_verdict,
            '\n'.join(explanation_parts),
            confidence=75,
            sources=['Multiple sources analyzed']
        )
    
    def _analyze_speaker_patterns(self, speaker: str, claim: str) -> Optional[str]:
        """Analyze speaker's historical patterns"""
        if not hasattr(self, 'fact_history'):
            return None
        
        patterns = []
        
        # Check for pattern of false promises
        empty_promises = self.fact_history.get_empty_promises_count(speaker)
        if empty_promises > 5:
            patterns.append(f"• {speaker} has made {empty_promises} similar vague promises without specific follow-through")
        
        # Check for pattern of exaggeration
        exaggerations = self.fact_history.get_exaggeration_count(speaker)
        if exaggerations > 10:
            patterns.append(f"• {speaker} frequently uses hyperbolic language ({exaggerations} documented instances)")
        
        # Check accuracy rate
        accuracy = self.fact_history.get_speaker_accuracy_rate(speaker)
        if accuracy and accuracy['total_claims'] > 20:
            patterns.append(f"• Overall fact-check record: {accuracy['true_percentage']:.1f}% accurate claims out of {accuracy['total_claims']} checked")
        
        return '\n'.join(patterns) if patterns else None
    
    def _get_balanced_context(self, claim: str) -> str:
        """Get balanced context for controversial claims"""
        claim_lower = claim.lower()
        
        if 'government' in claim_lower and ('crisis' in claim_lower or 'manage' in claim_lower):
            return """
• Supporting perspective: Critics point to specific challenges like border crossings (X million in Y period), inflation rates (Z% peak), supply chain disruptions, or international conflicts as evidence of management difficulties.
• Opposing perspective: Supporters cite unemployment rates (A%), GDP growth (B%), infrastructure spending ($C billion), or diplomatic achievements as signs of effective governance.
• Historical context: Every administration faces crises. Objective assessment requires comparing specific metrics across administrations using consistent methodologies.
• Data note: Cherry-picking statistics from either perspective can create misleading impressions. Comprehensive analysis requires examining multiple indicators over time."""
        
        elif 'catastrophic' in claim_lower or 'disaster' in claim_lower:
            return """
• These are subjective characterizations that different observers will evaluate differently based on their priorities and political perspectives.
• Objective analysis requires defining specific metrics for "catastrophic" or "disaster" and comparing current data to historical baselines.
• Without specific examples or measurable criteria, such characterizations remain in the realm of political opinion rather than verifiable fact."""
        
        elif 'respected' in claim_lower or 'world' in claim_lower:
            return """
• International respect is difficult to measure objectively. Possible metrics include:
  - Polling data from allied nations (varies by country and methodology)
  - Diplomatic achievements or setbacks (subjectively evaluated)
  - Trade relationships and economic indicators
  - Military alliances and security cooperation
• Different nations and populations have varying views based on their own interests and values.
• Claims about global opinion should be supported by specific data from credible international sources."""
        
        else:
            return """
• Political assessments often mix factual claims with value judgments and predictions.
• Different sources emphasize different metrics based on their priorities.
• Readers should seek specific data points and consider multiple perspectives when evaluating broad political claims.
• Be wary of absolute statements that lack supporting evidence or specific examples."""
    
    async def _check_with_ai_comprehensive(self, claim: str, is_opinion: bool = False) -> Dict:
        """Use AI for comprehensive fact-checking"""
        try:
            if is_opinion:
                prompt = f"""Analyze this opinion statement comprehensively:
Statement: "{claim}"

1. What specific, verifiable facts are implied or assumed?
2. What evidence supports this view? Be specific with data, dates, and sources.
3. What evidence contradicts this view? Be equally specific.
4. Is this empty rhetoric or does it contain substantive claims?
5. What context is important for understanding this fairly?

If this is just political rhetoric with no substance, say so directly. Provide a balanced analysis with specific examples."""
            else:
                prompt = f"""Fact-check this claim thoroughly:
Claim: "{claim}"

1. Break down each factual component
2. Check each component against available evidence
3. Note what can and cannot be verified
4. Identify any missing context that changes the meaning
5. Check if this is a prediction, promise, or factual claim

Provide a clear verdict and detailed explanation. If it's empty rhetoric, identify it as such."""

            response = self.openai_client.chat.completions.create(
                model='gpt-4' if hasattr(self.config, 'USE_GPT4') and self.config.USE_GPT4 else 'gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a thorough fact-checker. Identify empty rhetoric, analyze substance, and provide balanced perspective. Be direct about claims that lack substance."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            
            # Enhanced verdict detection for rhetoric
            verdict = 'needs_context'
            result_lower = result.lower()
            
            if any(phrase in result_lower for phrase in ['empty rhetoric', 'no substance', 'purely rhetorical', 'vague promise']):
                verdict = 'empty_rhetoric'
            elif 'true' in result_lower and 'false' not in result_lower:
                verdict = 'true'
            elif 'false' in result_lower and 'true' not in result_lower:
                verdict = 'false'
            elif 'mixed' in result_lower or 'partially' in result_lower:
                verdict = 'mixed'
            elif 'prediction' in result_lower or 'future claim' in result_lower:
                verdict = 'unsubstantiated_prediction'
            elif is_opinion:
                verdict = 'opinion'
            
            # Use full response for comprehensive explanation
            explanation = result
            confidence = self._extract_confidence(result)
            
            return {
                'found': True,
                'verdict': verdict,
                'explanation': explanation,
                'confidence': confidence,
                'source': 'Comprehensive AI Analysis',
                'weight': 0.8
            }
            
        except Exception as e:
            logger.error(f"AI comprehensive check error: {e}")
            return {'found': False}
    
    def _aggregate_results(self, claim: str, results: Dict, speaker: str, historical: Optional[Dict]) -> Dict:
        """Aggregate results from multiple sources into final verdict"""
        
        # Track findings
        verdicts = []
        explanations = []
        sources_used = []
        total_confidence = 0
        
        # Process each result
        for source, result in results.items():
            if result.get('found'):
                verdict = result.get('verdict')
                if verdict and verdict != 'needs_context':
                    weight = result.get('weight', 0.5)
                    confidence = result.get('confidence', 50)
                    
                    verdicts.append({
                        'verdict': verdict,
                        'weight': weight,
                        'confidence': confidence,
                        'source': source
                    })
                    
                    if result.get('explanation'):
                        explanations.append(f"{source.upper()}: {result['explanation']}")
                    
                    sources_used.append(result.get('source', source))
        
        # If no results found, try pattern matching
        if not verdicts:
            pattern_result = self._check_common_patterns(claim)
            if pattern_result:
                return pattern_result
            
            # For claims with implicit facts, provide analysis anyway
            if self._contains_implicit_facts(claim):
                return self._create_verdict(
                    'opinion',
                    'This appears to be an opinion containing factual implications. Without access to specific data sources, we cannot fully verify the underlying claims. Readers should seek primary sources and consider multiple perspectives.',
                    confidence=30
                )
            
            return self._create_verdict(
                'needs_context',
                'Unable to verify through available sources. This may be too vague or require specialized knowledge to fact-check properly.',
                confidence=30
            )
        
        # Check if any source identified this as empty rhetoric
        rhetoric_verdicts = [v for v in verdicts if v['verdict'] in ['empty_rhetoric', 'unsubstantiated_prediction']]
        if rhetoric_verdicts:
            # Rhetoric verdict takes precedence
            return self._create_verdict(
                rhetoric_verdicts[0]['verdict'],
                '\n\n'.join(explanations),
                confidence=max(v['confidence'] for v in rhetoric_verdicts),
                sources=sources_used
            )
        
        # Calculate weighted verdict for other cases
        verdict_scores = {
            'true': 1.0,
            'mostly_true': 0.8,
            'nearly_true': 0.7,
            'mixed': 0.5,
            'misleading': 0.3,
            'mostly_false': 0.2,
            'false': 0.0,
            'pattern_of_false_promises': 0.1
        }
        
        weighted_score = 0
        total_weight = 0
        verdict_count = defaultdict(int)
        
        for v in verdicts:
            verdict_type = self._normalize_verdict(v['verdict'])
            weight = v['weight']
            verdict_count[verdict_type] += 1
            
            if verdict_type in verdict_scores:
                weighted_score += verdict_scores[verdict_type] * weight
                total_weight += weight
                total_confidence += v['confidence'] * weight
        
        # Determine final verdict
        if total_weight > 0:
            final_score = weighted_score / total_weight
            avg_confidence = int(total_confidence / total_weight)
            
            if final_score >= 0.85:
                final_verdict = 'true'
            elif final_score >= 0.70:
                final_verdict = 'mostly_true'
            elif final_score >= 0.60:
                final_verdict = 'nearly_true'
            elif final_score >= 0.40:
                final_verdict = 'misleading'
            elif final_score >= 0.20:
                final_verdict = 'mostly_false'
            else:
                final_verdict = 'false'
        else:
            final_verdict = 'needs_context'
            avg_confidence = 30
        
        # Build comprehensive explanation
        explanation_parts = []
        
        # Add main findings
        if len(explanations) > 1:
            explanation_parts.append("ANALYSIS FROM MULTIPLE SOURCES:")
        explanation_parts.extend(explanations)
        
        # Add balanced context for controversial topics
        if self._is_controversial_topic(claim):
            explanation_parts.append("\n\nIMPORTANT CONTEXT:")
            explanation_parts.append(self._get_balanced_context(claim))
        
        # Add speaker pattern analysis
        if speaker != 'Unknown':
            pattern_analysis = self._analyze_speaker_patterns(speaker, claim)
            if pattern_analysis:
                explanation_parts.append(f"\n\nSPEAKER TRACK RECORD:\n{pattern_analysis}")
        
        # Add historical context
        if historical and historical.get('pattern'):
            explanation_parts.append(f"\n\nHISTORICAL NOTE: {speaker} has a documented pattern of {historical['pattern']}.")
        
        # Join all parts
        explanation = '\n\n'.join(explanation_parts) if explanation_parts else 'Based on available evidence.'
        
        return self._create_verdict(
            final_verdict,
            explanation,
            confidence=avg_confidence,
            sources=sources_used
        )
    
    def _is_controversial_topic(self, claim: str) -> bool:
        """Check if claim involves controversial topics needing balanced context"""
        controversial_keywords = [
            'government', 'administration', 'president', 'congress',
            'democrat', 'republican', 'liberal', 'conservative',
            'immigration', 'abortion', 'gun', 'climate', 'vaccine',
            'election', 'voter', 'fraud', 'crisis', 'border',
            'media', 'fake news', 'corruption', 'deep state'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in controversial_keywords)
    
    def _check_common_patterns(self, claim: str) -> Optional[Dict]:
        """Check common false claim patterns and empty rhetoric"""
        claim_lower = claim.lower()
        
        # First check for empty rhetoric
        rhetoric_result = self._check_empty_rhetoric(claim)
        if rhetoric_result:
            return rhetoric_result
        
        # Absolute statements that are usually false
        if re.search(r'\b(never|always|no one|everyone|all|none|every single|100%|0%)\b', claim_lower):
            if not re.search(r'\b\d+\s*%', claim):  # Unless it has specific percentages
                return self._create_verdict(
                    'mostly_false',
                    'This claim uses absolute language ("always," "never," "everyone," etc.) which is rarely accurate in complex real-world situations. Such sweeping generalizations typically ignore exceptions, nuance, and contradictory evidence. Specific data and examples would be needed to support such a categorical statement.',
                    confidence=70
                )
        
        # "First time ever" claims
        if 'first time' in claim_lower or 'never before' in claim_lower or 'unprecedented' in claim_lower:
            return self._create_verdict(
                'mostly_false',
                'Claims of unprecedented events or "firsts" are frequently incorrect. History often contains similar or comparable events that contradict such claims. Thorough historical research across multiple sources would be needed to verify something is truly unprecedented.',
                confidence=65
            )
        
        # Conspiracy theory indicators
        conspiracy_patterns = ['deep state', 'they don\'t want you to know', 'hidden agenda', 'media won\'t report']
        if any(pattern in claim_lower for pattern in conspiracy_patterns):
            return self._create_verdict(
                'needs_context',
                'This claim contains language commonly associated with conspiracy theories. Extraordinary claims require extraordinary evidence. Reliable, verifiable sources from multiple independent outlets would be needed to support such assertions.',
                confidence=40
            )
        
        return None
    
    def _extract_confidence(self, text: str) -> int:
        """Extract confidence from text"""
        # Look for confidence mentions
        pattern = r'(?:confidence|certainty):\s*(\d+)%?'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Check for rhetoric indicators
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in ['empty rhetoric', 'no substance', 'vague promise']):
            return 90  # High confidence it's rhetoric
        
        # Default based on language
        if any(word in text_lower for word in ['definitely', 'certainly', 'clearly']):
            return 90
        elif any(word in text_lower for word in ['likely', 'probably', 'appears']):
            return 70
        elif any(word in text_lower for word in ['possibly', 'might', 'could']):
            return 50
        else:
            return 60
    
    def _is_economic_claim(self, claim: str) -> bool:
        """Check if claim is about economic data"""
        economic_keywords = [
            'unemployment', 'inflation', 'gdp', 'economy', 'jobs',
            'wage', 'income', 'deficit', 'debt', 'budget', 'trade',
            'tariff', 'tax', 'revenue', 'spending', 'growth',
            'recession', 'stock market', 'dow jones', 'nasdaq'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in economic_keywords)
    
    def _is_government_data_claim(self, claim: str) -> bool:
        """Check if claim relates to government data"""
        gov_keywords = [
            'census', 'population', 'demographic', 'health', 'covid',
            'disease', 'climate', 'temperature', 'weather', 'storm',
            'immigration', 'crime', 'statistics', 'federal', 'state',
            'government', 'administration', 'policy', 'regulation',
            'congress', 'senate', 'house', 'supreme court'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in gov_keywords)
    
    def _is_academic_claim(self, claim: str) -> bool:
        """Check if claim relates to academic research"""
        academic_keywords = [
            'study', 'research', 'paper', 'journal', 'scientist',
            'professor', 'university', 'peer-reviewed', 'published',
            'findings', 'evidence', 'data shows', 'according to research',
            'analysis', 'experiment', 'survey', 'poll'
        ]
        claim_lower = claim.lower()
        return any(keyword in claim_lower for keyword in academic_keywords)
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict string"""
        verdict_map = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mostly_true': 'mostly_true',
            'nearly true': 'nearly_true',
            'misleading': 'misleading',
            'mostly false': 'mostly_false',
            'mostly_false': 'mostly_false',
            'false': 'false',
            'needs context': 'needs_context',
            'needs_context': 'needs_context',
            'opinion': 'opinion',
            'mixed': 'mixed',
            'empty rhetoric': 'empty_rhetoric',
            'empty_rhetoric': 'empty_rhetoric',
            'unsubstantiated prediction': 'unsubstantiated_prediction',
            'unsubstantiated_prediction': 'unsubstantiated_prediction',
            'pattern of false promises': 'pattern_of_false_promises',
            'pattern_of_false_promises': 'pattern_of_false_promises'
        }
        return verdict_map.get(verdict.lower().strip(), 'needs_context')
    
    def _create_verdict(self, verdict: str, explanation: str, confidence: int = 50, sources: List[str] = None) -> Dict:
        """Create standardized verdict"""
        return {
            'verdict': verdict,
            'verdict_details': VERDICT_CATEGORIES.get(verdict, VERDICT_CATEGORIES['needs_context']),
            'explanation': explanation,
            'confidence': confidence,
            'sources': sources or [],
            'timestamp': datetime.now().isoformat()
        }

# Make it compatible with existing code
class FactChecker(ComprehensiveFactChecker):
    """Wrapper for compatibility"""
    pass
