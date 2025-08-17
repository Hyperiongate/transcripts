"""
Services package for Transcript Fact Checker
"""
from .transcript import TranscriptProcessor
from .claims import ClaimsExtractor  # Changed from ClaimExtractor to ClaimsExtractor
from .factcheck import FactChecker

__all__ = ['TranscriptProcessor', 'ClaimsExtractor', 'FactChecker']  # Also fixed here
