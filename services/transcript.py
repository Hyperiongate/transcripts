"""
Transcript processing service
Handles various transcript formats and sources
"""
import re
import logging
from typing import Dict, Optional, List
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Import the audio transcriber
try:
    from .youtube_audio_transcriber import YouTubeAudioTranscriber
    AUDIO_TRANSCRIPTION_AVAILABLE = True
except ImportError:
    AUDIO_TRANSCRIPTION_AVAILABLE = False
    logging.warning("Audio transcription not available - missing dependencies")

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process transcripts from various sources"""
    
    def __init__(self):
        self.youtube_url_patterns = [
            # Standard watch URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            # Short URLs
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            # Embed URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            # Mobile URLs
            r'(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            # URLs with additional parameters
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
            # YouTube Music URLs
            r'(?:https?://)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
        ]
        
        # Initialize audio transcriber if available
        if AUDIO_TRANSCRIPTION_AVAILABLE:
            try:
                self.audio_transcriber = YouTubeAudioTranscriber()
                logger.info("Audio transcription initialized")
            except Exception as e:
                logger.error(f"Failed to initialize audio transcriber: {e}")
                self.audio_transcriber = None
        else:
            self.audio_transcriber = None
    
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
        """Extract transcript from YouTube video - tries captions first, then audio if available"""
        try:
            logger.info(f"Attempting to parse YouTube URL: {url}")
            
            # Extract video ID
            video_id = self._extract_youtube_id(url)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {url}")
                return {
                    'success': False,
                    'error': 'Invalid YouTube URL. Could not extract video ID.'
                }
            
            logger.info(f"Extracted video ID: {video_id}")
            
            # First, try to get captions (original method)
            caption_result = self._get_captions(video_id)
            
            if caption_result['success']:
                logger.info("Successfully extracted captions")
                return caption_result
            
            # If captions failed and audio transcriber is available, try audio transcription
            if self.audio_transcriber:
                logger.info("No captions available, attempting audio transcription...")
                logger.info("Note: Audio transcription may take 1-3 minutes depending on video length")
                
                audio_result = self.audio_transcriber.transcribe_youtube_video(url)
                
                if audio_result['success']:
                    logger.info("Successfully transcribed audio")
                    # Add video ID and ensure all expected fields are present
                    audio_result['video_id'] = video_id
                    audio_result['transcript'] = self.clean_transcript(audio_result['transcript'])
                    audio_result['format'] = 'youtube'
                    audio_result['word_count'] = len(audio_result['transcript'].split())
                    if 'source_type' not in audio_result:
                        audio_result['source_type'] = 'audio_transcription'
                    return audio_result
                else:
                    # Return specific error message
                    error_msg = caption_result.get('error', 'No captions available')
                    if 'audio transcription failed' not in error_msg:
                        error_msg += f". Audio transcription also failed: {audio_result.get('error', 'Unknown error')}"
                    return {
                        'success': False,
                        'error': error_msg
                    }
            else:
                # No audio transcriber available, return original caption error
                return caption_result
                
        except Exception as e:
            logger.error(f"YouTube parsing error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to extract transcript: {str(e)}'
            }
    
    def _get_captions(self, video_id: str) -> Dict:
        """Get captions from YouTube (original method)"""
        try:
            # Get available transcript languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get English transcript first
            transcript = None
            languages_available = []
            
            # First, try manually created English transcripts
            try:
                transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
                logger.info("Found manually created English transcript")
            except:
                # If no manual English transcript, try auto-generated
                try:
                    transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    logger.info("Found auto-generated English transcript")
                except:
                    # If no English transcript, get the first available one
                    for t in transcript_list:
                        languages_available.append(t.language_code)
                        if transcript is None:
                            transcript = t
                            logger.info(f"Using transcript in language: {t.language}")
            
            if transcript is None:
                return {
                    'success': False,
                    'error': f'No transcript available. Languages found: {", ".join(languages_available) if languages_available else "none"}'
                }
            
            # Fetch the transcript
            transcript_data = transcript.fetch()
            
            # Combine transcript segments
            full_transcript = ' '.join([segment['text'] for segment in transcript_data])
            
            # Calculate duration from last segment
            duration = 0
            if transcript_data:
                last_segment = transcript_data[-1]
                duration = last_segment['start'] + last_segment.get('duration', 0)
            
            # Get video title (construct from video ID if API doesn't provide)
            title = f"YouTube Video {video_id}"
            
            # Clean the transcript
            cleaned_transcript = self.clean_transcript(full_transcript)
            
            return {
                'success': True,
                'transcript': cleaned_transcript,
                'title': title,
                'video_id': video_id,
                'duration': duration,
                'format': 'youtube',
                'language': transcript.language if hasattr(transcript, 'language') else 'unknown',
                'is_generated': transcript.is_generated if hasattr(transcript, 'is_generated') else False,
                'word_count': len(cleaned_transcript.split()),
                'source_type': 'captions'
            }
            
        except TranscriptsDisabled:
            logger.error(f"Transcripts disabled for video: {video_id}")
            return {
                'success': False,
                'error': 'Transcripts are disabled for this video. The video owner has disabled captions.'
            }
        except NoTranscriptFound:
            logger.error(f"No transcript found for video: {video_id}")
            return {
                'success': False,
                'error': 'No transcript available for this video. This video does not have captions.'
            }
        except VideoUnavailable:
            logger.error(f"Video unavailable: {video_id}")
            return {
                'success': False,
                'error': 'Video is unavailable or private. Please check if the video is accessible.'
            }
        except Exception as e:
            logger.error(f"Error listing transcripts: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to access video transcripts: {str(e)}'
            }
    
    def parse_srt(self, content: str) -> Dict:
        """Parse SRT subtitle format"""
        try:
            # Remove SRT formatting
            lines = content.strip().split('\n')
            transcript_lines = []
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    i += 1
                    continue
                
                # Skip index line (numbers only)
                if line.isdigit():
                    i += 1
                    # Skip timestamp line
                    if i < len(lines) and '-->' in lines[i]:
                        i += 1
                    # Collect text lines until next index or empty line
                    while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                        transcript_lines.append(lines[i].strip())
                        i += 1
                else:
                    i += 1
            
            transcript = ' '.join(transcript_lines)
            cleaned = self.clean_transcript(transcript)
            
            return {
                'success': True,
                'transcript': cleaned,
                'format': 'srt',
                'word_count': len(cleaned.split())
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
            
            # Skip WEBVTT header and any metadata
            i = 0
            while i < len(lines) and (lines[i].startswith('WEBVTT') or lines[i].strip() == '' or lines[i].startswith('NOTE')):
                i += 1
            
            # Process the rest
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    i += 1
                    continue
                
                # Skip timestamp lines
                if '-->' in line:
                    i += 1
                    continue
                
                # Skip cue identifiers (lines before timestamps)
                if i + 1 < len(lines) and '-->' in lines[i + 1]:
                    i += 1
                    continue
                
                # Skip style blocks
                if line.startswith('STYLE') or line.startswith('::cue'):
                    # Skip until empty line
                    while i < len(lines) and lines[i].strip() != '':
                        i += 1
                    continue
                
                # Add text line
                # Remove VTT tags like <c>, </c>, <v>, etc.
                clean_line = re.sub(r'<[^>]+>', '', line)
                if clean_line.strip():
                    transcript_lines.append(clean_line.strip())
                i += 1
            
            transcript = ' '.join(transcript_lines)
            cleaned = self.clean_transcript(transcript)
            
            return {
                'success': True,
                'transcript': cleaned,
                'format': 'vtt',
                'word_count': len(cleaned.split())
            }
            
        except Exception as e:
            logger.error(f"VTT parsing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse VTT file: {str(e)}'
            }
    
    def clean_transcript(self, text: str) -> str:
        """Clean and normalize transcript text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove speaker labels (common patterns)
        text = re.sub(r'^\[.*?\]:', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[A-Z\s]+:', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\w+\s*>>', '', text, flags=re.MULTILINE)
        
        # Remove timestamp patterns
        text = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', text)
        text = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?', '', text)
        
        # Remove common YouTube auto-caption artifacts
        text = re.sub(r'\[Music\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[Applause\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[Laughter\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[.*?\]', '', text)  # Remove all bracketed content
        
        # Remove parenthetical stage directions
        text = re.sub(r'\([^)]*\)', '', text)
        
        # Fix spacing issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\s+([,.!?])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([,.!?])([A-Za-z])', r'\1 \2', text)  # Add space after punctuation if missing
        
        # Fix common caption errors
        text = re.sub(r'\.{2,}', '.', text)  # Multiple periods to single
        text = re.sub(r',{2,}', ',', text)  # Multiple commas to single
        text = re.sub(r'\s*-\s*-\s*', ' - ', text)  # Fix dashes
        
        # Ensure sentences are properly spaced
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
        
        # Trim and return
        return text.strip()
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        if not url:
            return None
        
        # Clean the URL
        url = url.strip()
        
        # Try each pattern
        for pattern in self.youtube_url_patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                # Validate video ID format (11 characters, alphanumeric + dash/underscore)
                if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                    return video_id
        
        # If no pattern matches, check if it's just a video ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            return url
        
        return None
    
    def validate_youtube_url(self, url: str) -> tuple[bool, str]:
        """Validate YouTube URL and return (is_valid, error_message)"""
        if not url or not url.strip():
            return False, "URL is empty"
        
        video_id = self._extract_youtube_id(url)
        if not video_id:
            return False, "Invalid YouTube URL format"
        
        return True, ""
