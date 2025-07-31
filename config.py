"""
Configuration for Transcript Fact Checker
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Primary Fact-Checking APIs
    GOOGLE_FACTCHECK_API_KEY = os.getenv('GOOGLE_FACTCHECK_API_KEY')
    
    # News and Media APIs
    NEWS_API_KEY = os.getenv('NEWS_API_KEY')  # newsapi.org
    
    # Web Scraping APIs (for accessing fact-checker sites)
    SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY')  # scraperapi.com
    SCRAPINGBEE_API_KEY = os.getenv('SCRAPINGBEE_API_KEY')  # scrapingbee.com
    
    # Optional AI Enhancement
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Processing Limits
    MAX_TRANSCRIPT_LENGTH = 50000  # characters
    MAX_CLAIMS_PER_TRANSCRIPT = 50
    MIN_CLAIM_LENGTH = 10
    MAX_CLAIM_LENGTH = 500
    
    # Fact Checking
    FACT_CHECK_CONFIDENCE_THRESHOLD = 0.7
    FACT_CHECK_BATCH_SIZE = 5
    FACT_CHECK_RATE_LIMIT_DELAY = 0.5  # seconds between API calls
    MIN_SOURCES_FOR_VERIFICATION = 2  # Minimum sources needed to verify
    
    # File Upload
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'txt', 'srt', 'vtt', 'json'}
    
    # Caching
    CACHE_TTL = 3600  # 1 hour
    
    # YouTube
    YOUTUBE_MAX_DURATION = 3600  # 1 hour max video duration
    
    # Export
    EXPORT_FORMATS = ['pdf', 'json', 'txt']
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        warnings = []
        
        if not cls.GOOGLE_FACTCHECK_API_KEY:
            warnings.append("GOOGLE_FACTCHECK_API_KEY not set - using limited analysis")
        
        if not cls.NEWS_API_KEY:
            warnings.append("NEWS_API_KEY not set - news verification disabled")
        
        if not cls.SCRAPERAPI_KEY and not cls.SCRAPINGBEE_API_KEY:
            warnings.append("No web scraping API keys - fact-checker site access limited")
        
        if warnings:
            print("⚠️  Configuration Status:")
            for warning in warnings:
                print(f"   - {warning}")
        else:
            print("✅ All API keys configured for enhanced fact-checking")
        
        return True
    
    @classmethod
    def get_active_apis(cls):
        """Return list of configured APIs"""
        active = []
        
        if cls.GOOGLE_FACTCHECK_API_KEY:
            active.append("Google Fact Check")
        if cls.NEWS_API_KEY:
            active.append("News API")
        if cls.SCRAPERAPI_KEY or cls.SCRAPINGBEE_API_KEY:
            active.append("Web Scraping")
            
        return active
