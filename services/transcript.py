"""
Transcript Processing Service
Handles cleaning and preprocessing of transcripts
"""
import re
import logging
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process and clean transcripts from various sources"""
    
    def __init__(self):
        self.youtube_regex = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
        )
    
    def process(self, input_text: str) -> str:
        """Process input text or URL and return clean transcript"""
        # Check if it's a YouTube URL
        youtube_match = self.youtube_regex.search(input_text)
        if youtube_match:
            video_id = youtube_match.group(1)
            return self.get_youtube_transcript(video_id)
        
        # Otherwise, treat as direct transcript
        return self.clean_transcript(input_text)
    
    def get_youtube_transcript(self, video_id: str) -> str:
        """Fetch transcript from YouTube video"""
        try:
            # Get transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine all segments
            full_text = ' '.join(segment['text'] for segment in transcript_list)
            
            # Clean the transcript
            return self.clean_transcript(full_text)
            
        except Exception as e:
            logger.error(f"Failed to fetch YouTube transcript: {str(e)}")
            raise ValueError(f"Could not fetch YouTube transcript: {str(e)}")
    
    def clean_transcript(self, text: str) -> str:
        """Clean and normalize transcript text"""
        # Remove timestamps like [00:00:00]
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
        text = re.sub(r'\[\d{2}:\d{2}\]', '', text)
        
        # Remove speaker timestamps like (00:00)
        text = re.sub(r'\(\d{2}:\d{2}:\d{2}\)', '', text)
        text = re.sub(r'\(\d{2}:\d{2}\)', '', text)
        
        # Remove music/sound effect notations
        text = re.sub(r'\[(?:music|applause|laughter|crosstalk)\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\((?:music|applause|laughter|crosstalk)\)', '', text, flags=re.IGNORECASE)
        
        # Fix spacing issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Ensure sentences end with proper punctuation
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # If line doesn't end with punctuation, add period
                if line and line[-1] not in '.!?':
                    line += '.'
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def extract_metadata(self, text: str) -> Dict:
        """Extract metadata from transcript"""
        metadata = {
            'speakers': [],
            'length': len(text),
            'word_count': len(text.split()),
            'has_timestamps': bool(re.search(r'\[\d{2}:\d{2}(?::\d{2})?\]', text))
        }
        
        # Extract speaker names (common patterns)
        speaker_patterns = [
            r'^([A-Z][A-Z\s\.]+):',  # ALL CAPS:
            r'^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]',  # [Speaker Name]
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?):',  # Speaker Name:
        ]
        
        lines = text.split('\n')
        for line in lines[:100]:  # Check first 100 lines
            for pattern in speaker_patterns:
                match = re.match(pattern, line)
                if match:
                    speaker = match.group(1).strip()
                    if speaker not in metadata['speakers'] and len(speaker) < 50:
                        metadata['speakers'].append(speaker)
        
        return metadata
    
    def segment_by_speaker(self, text: str) -> List[Dict[str, str]]:
        """Segment transcript by speaker turns"""
        segments = []
        current_speaker = None
        current_text = []
        
        # Speaker patterns
        speaker_pattern = re.compile(
            r'^(?:\[)?([A-Z][A-Z\s\.]+|\w+(?:\s+\w+)?):(?:\])?(.*)$'
        )
        
        lines = text.split('\n')
        
        for line in lines:
            match = speaker_pattern.match(line)
            
            if match:
                # New speaker found
                if current_speaker and current_text:
                    segments.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_text).strip()
                    })
                
                current_speaker = match.group(1).strip()
                remainder = match.group(2).strip()
                current_text = [remainder] if remainder else []
            else:
                # Continue with current speaker
                if line.strip():
                    current_text.append(line.strip())
        
        # Add final segment
        if current_speaker and current_text:
            segments.append({
                'speaker': current_speaker,
                'text': ' '.join(current_text).strip()
            })
        
        # If no speakers found, return whole text as one segment
        if not segments:
            segments.append({
                'speaker': 'Unknown',
                'text': text
            })
        
        return segments
    
    def is_valid_transcript(self, text: str) -> bool:
        """Check if text appears to be a valid transcript"""
        if not text or len(text) < 50:
            return False
        
        # Check for minimum word count
        word_count = len(text.split())
        if word_count < 10:
            return False
        
        # Check for excessive special characters (might be code/data)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\.\,\!\?\-\']', text)) / len(text)
        if special_char_ratio > 0.3:
            return False
        
        return True
