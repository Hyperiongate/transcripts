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
    
    # OpenAI Configuration - AGGRESSIVE SETTINGS
    USE_GPT4 = os.environ.get('USE_GPT4', 'True').lower() == 'true'
    OPENAI_MODEL = 'gpt-4-1106-preview' if USE_GPT4 else 'gpt-3.5-turbo'
    ENABLE_AI_CLAIMS_EXTRACTION = True
    ENABLE_AI_FACT_CHECKING = True
    ENABLE_SOURCE_ANALYSIS = True
    ENABLE_COMPREHENSIVE_SUMMARY = True
    ENABLE_AGGRESSIVE_CHECKING = True  # New setting
    FORCE_VERDICT_ON_ALL_CLAIMS = True  # New setting
    
    # Application limits - INCREASED FOR LONGER TRANSCRIPTS
    MAX_TRANSCRIPT_LENGTH = 500000  # Increased to 500k characters (~100 pages)
    MAX_CLAIMS_PER_TRANSCRIPT = 100  # Increased from 50
    MAX_CLAIM_LENGTH = 500  # characters per claim
    
    # Timeouts - INCREASED FOR THOROUGHNESS
    FACT_CHECK_TIMEOUT = 15  # seconds per claim (increased)
    TOTAL_ANALYSIS_TIMEOUT = 900  # 15 minutes total (increased)
    API_TIMEOUT = 10  # seconds for external API calls (increased)
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
    
    # Verdict thresholds - MORE AGGRESSIVE
    CONFIDENCE_THRESHOLD_FOR_VERDICT = 50  # Lower threshold (was 70)
    ALWAYS_PROVIDE_VERDICT = True  # Never return needs_context if possible
    
    @classmethod
    def validate(cls):
        """Validate configuration and return warnings"""
        warnings = []
        
        if not cls.GOOGLE_FACTCHECK_API_KEY:
            warnings.append("No Google Fact Check API key configured")
        
        if not cls.OPENAI_API_KEY:
            warnings.append("No OpenAI API key configured - AI fact-checking disabled")
        
        if cls.USE_IN_MEMORY_STORAGE:
            warnings.append("Using in-memory storage - data will be lost on restart")
        
        # Check for any fact-checking capability
        if not any([cls.GOOGLE_FACTCHECK_API_KEY, cls.OPENAI_API_KEY, cls.NEWS_API_KEY]):
            warnings.append("WARNING: No fact-checking APIs configured!")
        
        return warnings
