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
    
    # API Keys
    GOOGLE_FACTCHECK_API_KEY = os.getenv('GOOGLE_FACTCHECK_API_KEY')
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
        if not cls.GOOGLE_FACTCHECK_API_KEY:
            print("⚠️  Warning: GOOGLE_FACTCHECK_API_KEY not set. Fact checking will use mock data.")
        
        return True
