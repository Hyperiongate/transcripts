# Add these imports at the top of factcheck.py
import re
from datetime import datetime, timedelta

# Add this to your FactChecker class __init__ method:
def __init__(self):
    self.google_api_key = Config.GOOGLE_FACTCHECK_API_KEY
    self.news_api_key = getattr(Config, 'NEWS_API_KEY', None)
    self.scraperapi_key = getattr(Config, 'SCRAPERAPI_KEY', None)
    self.fred_api_key = getattr(Config, 'FRED_API_KEY', None)  # ADD THIS LINE
    
    self.session = requests.Session()
    
    # FRED series mapping for economic data
    self.fred_series = {
        'unemployment rate': 'UNRATE',
        'unemployment': 'UNRATE',
        'inflation': 'CPIAUCSL',
        'cpi': 'CPIAUCSL',
        'gdp': 'GDP',
        'interest rate': 'DFF',
        'federal funds': 'DFF',
        'mortgage rate': 'MORTGAGE30US',
        'gas price': 'GASREGW',
        'oil price': 'DCOILWTICO',
        'stock market': 'SP500',
        's&p 500': 'SP500',
        'dow jones': 'DJIA',
        'minimum wage': 'FEDMINNFRWG',
    }

# Add this method to your FactChecker class:
async def _check_fred_data(self, claim: str) -> Dict:
    """Verify economic claims against Federal Reserve data"""
    
    if not self.fred_api_key:
        return {'found': False}
    
    try:
        # Check if claim contains economic indicators
        claim_lower = claim.lower()
        series_to_check = []
        
        for term, series_id in self.fred_series.items():
            if term in claim_lower:
                series_to_check.append((term, series_id))
        
        if not series_to_check:
            return {'found': False}
        
        # Extract numbers from claim
        numbers = re.findall(r'(\d+\.?\d*)\s*%?', claim)
        if not numbers:
            return {'found': False}
        
        claimed_value = float(numbers[0])
        
        # Check the most relevant series
        term, series_id = series_to_check[0]
        
        # Get latest data from FRED
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': self.fred_api_key,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('observations'):
                        latest = data['observations'][0]
                        actual_value = float(latest['value'])
                        date = latest['date']
                        
                        # Compare claimed vs actual
                        difference = abs(actual_value - claimed_value)
                        percentage_diff = (difference / actual_value) * 100 if actual_value != 0 else 100
                        
                        # Determine verdict based on accuracy
                        if percentage_diff < 1:
                            verdict = 'true'
                            confidence = 95
                        elif percentage_diff < 5:
                            verdict = 'mostly_true'
                            confidence = 85
                        elif percentage_diff < 10:
                            verdict = 'mixed'
                            confidence = 70
                        elif percentage_diff < 20:
                            verdict = 'mostly_false'
                            confidence = 80
                        else:
                            verdict = 'false'
                            confidence = 90
                        
                        explanation = f"Federal Reserve data shows {term} is actually {actual_value}% as of {date}"
                        if verdict == 'true':
                            explanation = f"✓ Verified: {term} is {actual_value}% as of {date}"
                        elif verdict == 'false':
                            explanation = f"✗ Incorrect: {term} is actually {actual_value}% as of {date}, not {claimed_value}%"
                        
                        return {
                            'found': True,
                            'verdict': verdict,
                            'confidence': confidence,
                            'explanation': explanation,
                            'source': 'Federal Reserve Economic Data (FRED)',
                            'url': f'https://fred.stlouisfed.org/series/{series_id}',
                            'actual_value': actual_value,
                            'claimed_value': claimed_value,
                            'date': date,
                            'weight': 0.95  # High weight for official data
                        }
        
        return {'found': False}
        
    except Exception as e:
        logger.error(f"FRED API error: {str(e)}")
        return {'found': False}

# UPDATE your _async_check_claim method to include FRED:
async def _async_check_claim(self, claim: str) -> Dict:
    """Verify the truth of a claim using multiple methods"""
    
    # First, identify what type of claim this is
    claim_type = self._identify_claim_type(claim)
    
    # Check if it's an economic claim
    economic_terms = ['unemployment', 'inflation', 'gdp', 'interest rate', 'economy', 'jobs', 'mortgage', 'stock market']
    is_economic = any(term in claim.lower() for term in economic_terms)
    
    if is_economic:
        # Prioritize FRED for economic claims
        results = await asyncio.gather(
            self._check_fred_data(claim),  # CHECK FRED FIRST
            self._google_fact_check(claim),
            self._check_semantic_scholar(claim),
            self._search_news_verification(claim),
            return_exceptions=True
        )
    else:
        # Original verification for non-economic claims
        results = await asyncio.gather(
            self._google_fact_check(claim),
            self._check_semantic_scholar(claim),
            self._search_news_verification(claim),
            self._search_web_verification(claim),
            return_exceptions=True
        )
    
    # Process results focusing on TRUTH
    valid_results = [r for r in results if isinstance(r, dict) and r.get('found')]
    
    if not valid_results:
        return self._create_unverified_response(claim, "Cannot verify claim with available sources")
    
    # Synthesize based on agreement about TRUTH
    return self._synthesize_truth_verdict(claim, valid_results)
