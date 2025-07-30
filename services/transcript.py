"""
Transcript processing service
Handles various transcript formats and sources
"""
import re
import logging
from typing import Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process transcripts from various sources"""
    
    def __init__(self):
        self.youtube_url_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)'
        ]
    
    def parse_text(self, text: str) -> Dict:
        """Parse plain text transcript"""
        try:
            cleaned = self.clean_transcript(text)
            return {
                'success': True,
                'transcript': cleaned,
                'format': 'text',
                'word_count': len(cleaned.split())
            }
        except Exception as e:
            logger.error(f"Text parsing error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_youtube(self, url: str) -> Dict:
        """Extract transcript from YouTube video"""
        try:
            # Extract video ID
            video_id = self._extract_youtube_id(url)
            if not video_id:
                return {
                    'success': False,
                    'error': 'Invalid YouTube URL'
                }
            
            # Get transcript
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                
                # Combine transcript segments
                full_transcript = ' '.join([segment['text'] for segment in transcript_list])
                
                # Get video title (would need additional API for full metadata)
                title = f"YouTube Video {video_id}"
                
                return {
                    'success': True,
                    'transcript': self.clean_transcript(full_transcript),
                    'title': title,
                    'video_id': video_id,
                    'duration': transcript_list[-1]['start'] + transcript_list[-1]['duration'] if transcript_list else 0,
                    'format': 'youtube'
                }
                
            except TranscriptsDisabled:
                return {
                    'success': False,
                    'error': 'Transcripts are disabled for this video'
                }
            except NoTranscriptFound:
                return {
                    'success': False,
                    'error': 'No transcript available for this video'
                }
            except VideoUnavailable:
                return {
                    'success': False,
                    'error': 'Video is unavailable or private'
                }
                
        except Exception as e:
            logger.error(f"YouTube parsing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to extract transcript: {str(e)}'
            }
    
    def parse_srt(self, content: str) -> Dict:
        """Parse SRT subtitle format"""
        try:
            # Remove SRT formatting
            lines = content.strip().split('\n')
            transcript_lines = []
            
            i = 0
            while i < len(lines):
                # Skip index line
                if lines[i].strip().isdigit():
                    i += 1
                    # Skip timestamp line
                    if i < len(lines) and '-->' in lines[i]:
                        i += 1
                    # Collect text lines
                    while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                        transcript_lines.append(lines[i].strip())
                        i += 1
                else:
                    i += 1
            
            transcript = ' '.join(transcript_lines)
            return {
                'success': True,
                'transcript': self.clean_transcript(transcript),
                'format': 'srt'
            }
            
        except Exception as e:
            logger.error(f"SRT parsing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse SRT file: {str(e)}'
            }
    
    def parse_vtt(self, content: str) -> Dict:
        """Parse WebVTT subtitle format"""
        try:
            # Remove VTT header and formatting
            lines = content.strip().split('\n')
            transcript_lines = []
            
            # Skip WEBVTT header
            start_index = 0
            if lines[0].startswith('WEBVTT'):
                start_index = 1
            
            i = start_index
            while i < len(lines):
                line = lines[i].strip()
                # Skip timestamp lines
                if '-->' in line or line == '':
                    i += 1
                    continue
                # Skip note/style blocks
                if line.startswith('NOTE') or line.startswith('STYLE'):
                    # Skip until empty line
                    while i < len(lines) and lines[i].strip() != '':
                        i += 1
                else:
                    # Add text line
                    transcript_lines.append(line)
                    i += 1
            
            transcript = ' '.join(transcript_lines)
            return {
                'success': True,
                'transcript': self.clean_transcript(transcript),
                'format': 'vtt'
            }
            
        except Exception as e:
            logger.error(f"VTT parsing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse VTT file: {str(e)}'
            }
    
    def clean_transcript(self, text: str) -> str:
        """Clean and normalize transcript text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove speaker labels (common patterns)
        text = re.sub(r'^\[.*?\]:', '', text, flags=re.MULTILINE)
        text = re.sub(r'^.*?:', '', text, flags=re.MULTILINE)
        
        # Remove timestamp patterns
        text = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', text)
        text = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?', '', text)
        
        # Remove common artifacts
        text = re.sub(r'\[.*?\]', '', text)  # Remove bracketed content
        text = re.sub(r'\(.*?\)', '', text)  # Remove parenthetical content
        
        # Clean up punctuation
        text = re.sub(r'\.{2,}', '.', text)  # Multiple periods to single
        text = re.sub(r'\s+([,.!?])', r'\1', text)  # Remove space before punctuation
        
        # Ensure sentences end with proper punctuation
        sentences = text.split('.')
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence[-1] in '.!?':
                sentence += '.'
            if sentence:
                cleaned_sentences.append(sentence)
        
        return ' '.join(cleaned_sentences)
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        for pattern in self.youtube_url_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
