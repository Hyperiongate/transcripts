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
    
    # API Keys
    GOOGLE_FACTCHECK_API_KEY = os.environ.get('GOOGLE_FACTCHECK_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    FRED_API_KEY = os.environ.get('FRED_API_KEY')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # Application limits
    MAX_TRANSCRIPT_LENGTH = 50000  # characters
    MAX_CLAIMS_TO_CHECK = 50  # maximum claims per analysis
    MAX_CLAIM_LENGTH = 500  # characters per claim
    
    # Timeouts
    FACT_CHECK_TIMEOUT = 10  # seconds per claim
    TOTAL_ANALYSIS_TIMEOUT = 300  # 5 minutes total
    API_TIMEOUT = 5  # seconds for external API calls
    
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
            warnings.append("OpenAI API key not set - AI filtering disabled")
        
        if cls.DEBUG:
            warnings.append("Running in DEBUG mode - not for production")
        
        return warnings
