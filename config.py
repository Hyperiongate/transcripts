"""
Enhanced Configuration File for Fact Checker Application
"""
import os
from datetime import timedelta

class Config:
    """Configuration for fact-checking application"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Server settings
    PORT = int(os.environ.get('PORT', 5000))
    
    # Database settings - with proper defaults
    MONGODB_URI = os.environ.get('MONGODB_URI', None)
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'factchecker')
    REDIS_URL = os.environ.get('REDIS_URL', None)
    
    # Use in-memory storage if databases not available
    USE_IN_MEMORY_STORAGE = MONGODB_URI is None or REDIS_URL is None
    
    # API Keys - ALL OF THEM
    GOOGLE_FACTCHECK_API_KEY = os.environ.get('GOOGLE_FACTCHECK_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    FRED_API_KEY = os.environ.get('FRED_API_KEY')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
    SCRAPERAPI_KEY = os.environ.get('SCRAPERAPI_KEY')
    SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY')
    MEDIASTACK_API_KEY = os.environ.get('MEDIASTACK_API_KEY')
    NOAA_TOKEN = os.environ.get('NOAA_TOKEN')
    CENSUS_API_KEY = os.environ.get('CENSUS_API_KEY')
    CDC_API_KEY = os.environ.get('CDC_API_KEY')
    
    # OpenAI Configuration
    USE_GPT4 = os.environ.get('USE_GPT4', 'True').lower() == 'true'
    OPENAI_MODEL = 'gpt-4-1106-preview' if USE_GPT4 else 'gpt-3.5-turbo'
    ENABLE_AI_CLAIMS_EXTRACTION = True
    ENABLE_AI_FACT_CHECKING = True
    ENABLE_SOURCE_ANALYSIS = True
    ENABLE_COMPREHENSIVE_SUMMARY = True
    
    # Application limits - INCREASED FOR LONGER TRANSCRIPTS
    MAX_TRANSCRIPT_LENGTH = 500000  # Increased to 500k characters (~100 pages)
    MAX_CLAIMS_PER_TRANSCRIPT = 50  # maximum claims per analysis
    MAX_CLAIM_LENGTH = 500  # characters per claim
    
    # Timeouts
    FACT_CHECK_TIMEOUT = 10  # seconds per claim
    TOTAL_ANALYSIS_TIMEOUT = 600  # 10 minutes total (increased from 5)
    API_TIMEOUT = 5  # seconds for external API calls
    REQUEST_TIMEOUT = 30  # seconds for HTTP requests
    
    # Caching
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 3600  # 1 hour
    
    # File upload settings
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'txt', 'srt', 'vtt'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Job storage
    JOB_STORAGE_TYPE = os.environ.get('JOB_STORAGE_TYPE', 'memory')
    JOB_RETENTION_HOURS = 24
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        warnings = []
        
        if not cls.GOOGLE_FACTCHECK_API_KEY:
            warnings.append("Google Fact Check API key not set - fact checking will be limited")
        
        if not cls.OPENAI_API_KEY:
            warnings.append("OpenAI API key not set - AI features disabled")
        else:
            if cls.USE_GPT4:
                warnings.append("Using GPT-4 for enhanced accuracy (higher cost)")
            else:
                warnings.append("Using GPT-3.5-turbo (lower cost, good performance)")
        
        # Check for additional APIs
        if not cls.NEWS_API_KEY:
            warnings.append("News API key not set - news verification disabled")
        
        if not cls.SCRAPERAPI_KEY:
            warnings.append("ScraperAPI key not set - web search verification limited")
            
        if not cls.FRED_API_KEY:
            warnings.append("FRED API key not set - economic data verification disabled")
        
        if cls.DEBUG:
            warnings.append("Running in DEBUG mode - not for production")
        
        if cls.USE_IN_MEMORY_STORAGE:
            warnings.append("Using in-memory storage - data will not persist between restarts")
        
        return warnings
