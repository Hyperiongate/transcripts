"""
Configuration for Transcript Fact Checker
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
    
    # MongoDB - with proper defaults for local/Render
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'factchecker')
    
    # Redis - with proper defaults for local/Render
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # API Keys
    GOOGLE_FACTCHECK_API_KEY = os.environ.get('GOOGLE_FACTCHECK_API_KEY', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    FRED_API_KEY = os.environ.get('FRED_API_KEY', '')
    
    # Application limits
    MAX_TRANSCRIPT_LENGTH = int(os.environ.get('MAX_TRANSCRIPT_LENGTH', 50000))
    MAX_CLAIMS_PER_TRANSCRIPT = int(os.environ.get('MAX_CLAIMS_PER_TRANSCRIPT', 50))
    
    # Timeouts
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))
    FACT_CHECK_TIMEOUT = int(os.environ.get('FACT_CHECK_TIMEOUT', 10))
