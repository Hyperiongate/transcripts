"""
Enhanced Fact-Checking Module with Comprehensive OpenAI Integration
Maximizes use of OpenAI for superior fact-checking accuracy
"""
import re
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time

logger = logging.getLogger(__name__)

class EnhancedFactChecker:
    """Enhanced fact checker with comprehensive OpenAI integration"""
    
    def __init__(self, config):
        self.google_api_key = config.GOOGLE_FACTCHECK_API_KEY
        self.openai_api_key = config.OPENAI_API_KEY
        self.fred_api_key = config.FRED_API_KEY
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        
        # Enhanced verdict options
        self.verdict_options = [
            'true',
            'mostly_true',
            'mixed',
            'unclear',
            'misleading',
            'lacks_context',
            'mostly_false',
            'false',
            'unverified',
            'opinion'
        ]
        
        # Configuration for enhanced AI usage
        self.use_gpt4 = True  # Use GPT-4 for better accuracy
        self.enable_source_analysis = True
        self.enable_context_enhancement = True
        self.enable_claim_relationships = True
        
        # Conversational patterns to filter
        self.conversational_patterns = [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)",
            r"^(thank you|thanks|appreciate)",
            r"^it'?s (good|nice|great) to (see|be)",
            r"^(i'?m |we'?re )(glad|happy|pleased|excited)",
            r"^(welcome|congratulations)",
            r"^(how are you|how'?s everyone)",
            r"^(please|let me|allow me)",
            r"^(um|uh|er|ah|oh|well)",
        ]
        
        # Track similar claims for consistency
        self.claim_comparison_cache = {}
        
    def check_claims_batch(self, claims: List[str], source: str = None) -> List[Dict]:
        """Check claims with comprehensive AI analysis"""
        if not claims:
            return []
        
        # Step 1: Use AI to filter and categorize claims
        filtered_claims = self._ai_filter_claims(claims) if self.openai_client else claims
        
        # Step 2: Analyze claim relationships
        if self.openai_client and self.enable_claim_relationships:
            claim_relationships = self._analyze_claim_relationships(filtered_claims)
        else:
            claim_relationships = {}
        
        # Step 3: Check each claim with AI-first approach
        results = []
        context_summary = self._generate_context_summary(filtered_claims) if self.openai_client else ""
        
        for i, claim in enumerate(filtered_claims):
            logger.info(f"Checking claim {i+1}/{len(filtered_claims)}: {claim[:80]}...")
            
            try:
                # AI-first comprehensive check
                result = self._check_claim_ai_first(claim, context_summary, claim_relationships)
                results.append(result)
            except Exception as e:
                logger.error(f"Error checking claim: {str(e)}")
                results.append({
                    'claim': claim,
                    'verdict': 'error',
                    'confidence': 0,
                    'explanation': f'Error during fact-check: {str(e)}',
                    'sources': []
                })
            
            # Minimal rate limiting since we have budget
            time.sleep(0.2)
        
        # Step 4: Generate comprehensive summary
        if self.openai_client and results:
            summary = self._generate_fact_check_summary(results, source)
            # Add summary to first result for easy access
            if results:
                results[0]['overall_summary'] = summary
        
        return results
    
    def _ai_filter_claims(self, claims: List[str]) -> List[str]:
        """Use AI to intelligently filter claims"""
        if not self.openai_client or not claims:
            return claims
        
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            claims_text = "\n".join([f"{i+1}. {claim}" for i, claim in enumerate(claims)])
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": """You are an expert at identifying factual claims that can be verified.
Filter out: greetings, opinions, vague statements, procedural language.
Keep: specific facts, statistics, historical claims, policy statements, verifiable assertions."""},
                    {"role": "user", "content": f"""Review these statements and return ONLY the numbers of verifiable factual claims.
Format: Return a comma-separated list of numbers (e.g., "1,3,5,8")

Statements:
{claims_text}"""}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            # Parse response
            numbers_text = response.choices[0].message.content.strip()
            claim_indices = [int(n.strip()) - 1 for n in numbers_text.split(',') if n.strip().isdigit()]
            
            filtered = [claims[i] for i in claim_indices if 0 <= i < len(claims)]
            logger.info(f"AI filtered {len(claims)} claims down to {len(filtered)}")
            return filtered if filtered else claims
            
        except Exception as e:
            logger.error(f"AI filtering error: {e}")
            return claims
    
    def _analyze_claim_relationships(self, claims: List[str]) -> Dict:
        """Analyze relationships between claims"""
        if not self.openai_client or not claims:
            return {}
        
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            claims_text = "\n".join([f"{i+1}. {claim}" for i, claim in enumerate(claims)])
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing logical relationships between claims."},
                    {"role": "user", "content": f"""Analyze these claims and identify:
1. Which claims contradict each other
2. Which claims support each other
3. Which claims are about the same topic
4. Key themes across all claims

Claims:
{claims_text}

Format your response as JSON."""}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse response
            try:
                relationships = json.loads(response.choices[0].message.content)
                return relationships
            except:
                return {}
                
        except Exception as e:
            logger.error(f"Relationship analysis error: {e}")
            return {}
    
    def _generate_context_summary(self, claims: List[str]) -> str:
        """Generate a context summary of all claims"""
        if not self.openai_client or not claims:
            return ""
        
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            claims_text = "\n".join([f"- {claim}" for claim in claims[:20]])  # Limit to first 20
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert at understanding context and themes."},
                    {"role": "user", "content": f"""Analyze these claims and provide a brief context summary including:
- Main topic/theme
- Time period referenced
- Key figures mentioned
- Overall narrative

Claims:
{claims_text}

Keep the summary under 150 words."""}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Context summary error: {e}")
            return ""
    
    def _check_claim_ai_first(self, claim: str, context_summary: str, relationships: Dict) -> Dict:
        """Check claim with AI-first approach"""
        result = {
            'claim': claim,
            'verdict': 'unverified',
            'confidence': 0,
            'explanation': '',
            'sources': [],
            'ai_analysis': {},
            'credibility_factors': {}
        }
        
        # Step 1: Comprehensive AI analysis
        if self.openai_client:
            ai_result = self._comprehensive_ai_check(claim, context_summary)
            if ai_result:
                result.update(ai_result)
                
                # If AI has high confidence, we can trust it
                if ai_result.get('confidence', 0) >= 80:
                    return result
        
        # Step 2: Cross-reference with Google Fact Check for additional validation
        if self.google_api_key:
            google_result = self._check_google_factcheck(claim)
            if google_result.get('found'):
                # Merge results intelligently
                result = self._merge_results(result, google_result)
        
        # Step 3: Enhance with source credibility analysis
        if self.openai_client and self.enable_source_analysis:
            credibility = self._analyze_source_credibility(claim, result.get('sources', []))
            result['credibility_factors'] = credibility
        
        return result
    
    def _comprehensive_ai_check(self, claim: str, context: str = "") -> Optional[Dict]:
        """Comprehensive fact-checking using AI"""
        if not self.openai_client:
            return None
        
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            # Extract temporal context
            temporal_info = self._extract_temporal_context(claim)
            temporal_context = f"\nTemporal context: {json.dumps(temporal_info)}" if temporal_info else ""
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": """You are an expert fact-checker with access to knowledge up to April 2024.
Analyze claims for factual accuracy, considering context, nuance, and potential interpretations.
Be rigorous but fair. Consider what the speaker likely meant, not just literal words."""},
                    {"role": "user", "content": f"""Fact-check this claim with comprehensive analysis.

Context: {context}
{temporal_context}

Claim: "{claim}"

Provide your analysis in JSON format with these fields:
{{
    "verdict": "true/mostly_true/mixed/unclear/misleading/lacks_context/mostly_false/false/unverified",
    "confidence": 0-100,
    "explanation": "detailed explanation",
    "interpretation": "what the speaker appears to be claiming",
    "key_issues": ["list of any issues"],
    "missing_context": "any critical missing context",
    "fact_check_notes": "additional notes for fact-checkers",
    "sources_needed": ["suggested sources to verify"],
    "related_facts": ["relevant related facts"]
}}"""}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse response
            try:
                result = json.loads(response.choices[0].message.content)
                
                # Ensure all required fields
                return {
                    'verdict': result.get('verdict', 'unverified'),
                    'confidence': result.get('confidence', 50),
                    'explanation': result.get('explanation', ''),
                    'ai_analysis': result,
                    'sources': ['AI Analysis (GPT-4)' if self.use_gpt4 else 'AI Analysis (GPT-3.5)'],
                    'interpretation': result.get('interpretation', ''),
                    'missing_context': result.get('missing_context'),
                    'fact_check_notes': result.get('fact_check_notes')
                }
            except json.JSONDecodeError:
                # Fallback to text parsing
                text = response.choices[0].message.content
                return {
                    'verdict': 'unverified',
                    'confidence': 50,
                    'explanation': text,
                    'sources': ['AI Analysis'],
                    'ai_analysis': {'raw_response': text}
                }
                
        except Exception as e:
            logger.error(f"Comprehensive AI check error: {e}")
            return None
    
    def _analyze_source_credibility(self, claim: str, sources: List[str]) -> Dict:
        """Analyze credibility of sources"""
        if not self.openai_client:
            return {}
        
        try:
            model = "gpt-3.5-turbo"  # Use faster model for this
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating source credibility."},
                    {"role": "user", "content": f"""Evaluate the credibility of these sources for fact-checking this claim:

Claim: "{claim}"
Sources: {', '.join(sources) if sources else 'No sources available'}

Provide a brief credibility assessment including:
- Overall credibility (High/Medium/Low)
- Potential biases
- Recommendations for additional sources

Format as JSON."""}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            try:
                return json.loads(response.choices[0].message.content)
            except:
                return {'assessment': response.choices[0].message.content}
                
        except Exception as e:
            logger.error(f"Source credibility analysis error: {e}")
            return {}
    
    def _generate_fact_check_summary(self, results: List[Dict], source: str = None) -> Dict:
        """Generate comprehensive summary of fact-checking results"""
        if not self.openai_client or not results:
            return {}
        
        try:
            model = "gpt-4-1106-preview" if self.use_gpt4 else "gpt-3.5-turbo"
            
            # Prepare results summary
            results_text = ""
            for i, result in enumerate(results[:30], 1):  # Limit to 30 results
                results_text += f"\n{i}. Claim: {result['claim'][:100]}...\n"
                results_text += f"   Verdict: {result['verdict']} (Confidence: {result.get('confidence', 0)}%)\n"
                results_text += f"   Explanation: {result.get('explanation', 'N/A')[:200]}...\n"
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": """You are an expert at synthesizing fact-check results into clear, actionable summaries."""},
                    {"role": "user", "content": f"""Analyze these fact-check results and provide a comprehensive summary:

Source: {source or 'Unknown'}
Results:
{results_text}

Create a summary including:
1. Overall credibility assessment
2. Key patterns in false/misleading claims
3. Main topics covered
4. Critical findings that need attention
5. Recommendations for readers

Format as JSON with these sections."""}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            try:
                return json.loads(response.choices[0].message.content)
            except:
                return {'summary': response.choices[0].message.content}
                
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return {}
    
    def _merge_results(self, ai_result: Dict, google_result: Dict) -> Dict:
        """Intelligently merge AI and Google results"""
        merged = ai_result.copy()
        
        # If Google has a different verdict, note it
        if google_result.get('verdict') != ai_result.get('verdict'):
            merged['cross_reference'] = {
                'google_verdict': google_result.get('verdict'),
                'google_explanation': google_result.get('explanation'),
                'google_sources': google_result.get('sources', [])
            }
            
            # Add Google sources
            merged['sources'].extend(google_result.get('sources', []))
            
            # If Google has higher confidence on false claims, defer to it
            if google_result.get('verdict') in ['false', 'mostly_false'] and google_result.get('confidence', 0) > 80:
                merged['verdict'] = google_result['verdict']
                merged['explanation'] = f"Google Fact Check: {google_result['explanation']}\n\nAI Analysis: {merged['explanation']}"
        
        return merged
    
    def _check_google_factcheck(self, claim: str) -> Dict:
        """Check claim using Google Fact Check API"""
        try:
            if not self.google_api_key:
                return {'found': False}
            
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                'key': self.google_api_key,
                'query': claim,
                'pageSize': 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'claims' in data and data['claims']:
                    # Process first relevant claim
                    for claim_review in data['claims']:
                        if claim_review.get('claimReview'):
                            review = claim_review['claimReview'][0]
                            
                            verdict = self._normalize_verdict(review.get('textualRating', 'unverified'))
                            
                            return {
                                'found': True,
                                'verdict': verdict,
                                'confidence': 85,
                                'explanation': review.get('title', ''),
                                'sources': [review.get('publisher', {}).get('name', 'Unknown')],
                                'api_response': True
                            }
            
            return {'found': False}
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {str(e)}")
            return {'found': False}
    
    def _normalize_verdict(self, verdict: str) -> str:
        """Normalize verdict strings to standard format"""
        verdict_lower = verdict.lower().strip()
        
        mapping = {
            'true': 'true',
            'mostly true': 'mostly_true',
            'mostly-true': 'mostly_true',
            'half true': 'mixed',
            'half-true': 'mixed',
            'mixed': 'mixed',
            'mostly false': 'mostly_false',
            'mostly-false': 'mostly_false',
            'false': 'false',
            'pants on fire': 'false',
            'incorrect': 'false',
            'misleading': 'misleading',
            'unverified': 'unverified',
            'unproven': 'unverified',
            'unknown': 'unverified'
        }
        
        return mapping.get(verdict_lower, 'unverified')
    
    def _extract_temporal_context(self, claim: str) -> Dict:
        """Extract temporal context from claim"""
        temporal_info = {}
        
        # Check for year references
        year_match = re.search(r'\b(20\d{2})\b', claim)
        if year_match:
            year = int(year_match.group(1))
            temporal_info['year'] = year
            
            # Check if referring to partial year
            current_year = datetime.now().year
            if year == current_year:
                temporal_info['partial_year'] = True
                temporal_info['current_date'] = datetime.now().strftime('%B %d, %Y')
            
            # Check for specific time references
            if re.search(r'(so far|thus far|to date|as of|through)', claim, re.IGNORECASE):
                temporal_info['partial_period'] = True
        
        # Check for relative time references
        if re.search(r'(last|previous|past) (year|month|week)', claim, re.IGNORECASE):
            temporal_info['relative_time'] = True
        
        return temporal_info

# Main FactChecker class
class FactChecker(EnhancedFactChecker):
    """Main FactChecker class with all enhancements"""
    
    def __init__(self, config):
        """Initialize FactChecker with configuration"""
        super().__init__(config)
        
    def check_claims(self, claims: List[str], context: Dict = None) -> List[Dict]:
        """Check multiple claims and return results
        
        Args:
            claims: List of claim strings to check
            context: Optional context dictionary with metadata
            
        Returns:
            List of fact check results with verdicts and explanations
        """
        # Validate input
        if not claims:
            return []
            
        # Extract source from context if provided
        source = None
        if context and isinstance(context, dict):
            source = context.get('source')
            
        # Use the comprehensive batch checking method
        return self.check_claims_batch(claims, source=source)
