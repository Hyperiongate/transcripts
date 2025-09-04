"""
YouTube Transcript Service - REALISTIC IMPLEMENTATION
Handles what's actually possible with YouTube content
"""
import os
import re
import logging
import tempfile
from typing import Dict, Optional, List
from datetime import datetime

# Only import what we actually have
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class YouTubeService:
    """
    Realistic YouTube transcript extraction service.
    NO LIVE STREAMING - Only completed videos.
    """
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        logger.info("YouTube Service initialized - Video transcripts only (no live streaming)")
    
    def process_youtube_url(self, url: str) -> Dict:
        """
        Main entry point for YouTube URL processing.
        Attempts multiple methods in order of preference.
        
        Returns:
            Dict with status, transcript, and metadata
        """
        try:
            # Extract video ID
            video_id = self._extract_video_id(url)
            if not video_id:
                return {
                    'success': False,
                    'error': 'Invalid YouTube URL format',
                    'suggestion': 'Please provide a standard YouTube video URL'
                }
            
            # Check if this is a live stream (and reject if so)
            if self._is_live_stream(url):
                return {
                    'success': False,
                    'error': 'Live streams cannot be processed in real-time',
                    'suggestion': 'Please wait for the stream to end and process the recorded version',
                    'alternative': 'Use the microphone feature to transcribe audio playing from your speakers'
                }
            
            # Method 1: Try to get existing captions (fastest and most accurate)
            caption_result = self._get_existing_captions(video_id)
            if caption_result['success']:
                logger.info(f"Successfully extracted captions for video {video_id}")
                return caption_result
            
            # Method 2: Check if we should attempt audio transcription
            video_info = self._get_video_info(url)
            if not video_info:
                return {
                    'success': False,
                    'error': 'Could not retrieve video information',
                    'suggestion': 'The video might be private, deleted, or region-locked'
                }
            
            duration = video_info.get('duration', 0)
            
            # Check duration limits
            if duration > 1800:  # 30 minutes
                return {
                    'success': False,
                    'error': f'Video is {duration//60} minutes long. Maximum 30 minutes for audio transcription.',
                    'suggestion': 'For longer videos, try videos with captions enabled',
                    'caption_status': caption_result.get('error', 'No captions available')
                }
            
            # Method 3: Download and transcribe audio (last resort)
            logger.info(f"Attempting audio transcription for {video_id}")
            audio_result = self._transcribe_audio_method(url, video_info)
            
            if audio_result['success']:
                return audio_result
            else:
                # Provide comprehensive error with all attempted methods
                return {
                    'success': False,
                    'error': 'Could not extract transcript from video',
                    'attempts': {
                        'captions': caption_result.get('error'),
                        'audio': audio_result.get('error')
                    },
                    'suggestion': 'Try a different video or use the microphone feature'
                }
                
        except Exception as e:
            logger.error(f"YouTube processing error: {str(e)}")
            return {
                'success': False,
                'error': f'Processing failed: {str(e)}',
                'suggestion': 'Please check the URL and try again'
            }
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
            r'(?:youtu\.be\/)([\w-]+)',
            r'(?:youtube\.com\/v\/)([\w-]+)',
            r'(?:youtube\.com\/shorts\/)([\w-]+)'  # Added shorts support
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _is_live_stream(self, url: str) -> bool:
        """Check if URL is a live stream"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True  # Don't download, just get info
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                is_live = info.get('is_live', False)
                
                # Also check if it's a premiere (scheduled stream)
                if info.get('live_status') == 'is_upcoming':
                    return True
                    
                return is_live
                
        except Exception as e:
            logger.warning(f"Could not determine if video is live: {e}")
            return False
    
    def _get_video_info(self, url: str) -> Optional[Dict]:
        """Get video metadata"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'upload_date': info.get('upload_date', ''),
                    'description': info.get('description', '')[:500],  # First 500 chars
                    'is_live': info.get('is_live', False),
                    'was_live': info.get('was_live', False),
                    'video_id': info.get('id', '')
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def _get_existing_captions(self, video_id: str) -> Dict:
        """Try to get existing captions from YouTube"""
        try:
            # Try to get transcript list
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prefer manually created captions over auto-generated
            try:
                # Try to find manual captions in English
                transcript = transcript_list.find_manually_created_transcript(['en'])
                caption_type = 'manual'
            except:
                try:
                    # Fall back to auto-generated
                    transcript = transcript_list.find_generated_transcript(['en'])
                    caption_type = 'auto-generated'
                except:
                    # Try any available language
                    for transcript in transcript_list:
                        caption_type = 'auto-translated' if transcript.is_translatable else 'other-language'
                        break
                    else:
                        raise NoTranscriptFound("No transcripts found in any language")
            
            # Fetch the actual transcript
            transcript_data = transcript.fetch()
            
            # Combine all text
            full_text = ' '.join([entry['text'] for entry in transcript_data])
            
            # Clean up the text
            full_text = self._clean_transcript_text(full_text)
            
            return {
                'success': True,
                'transcript': full_text,
                'source_type': 'youtube_captions',
                'caption_type': caption_type,
                'language': transcript.language if 'transcript' in locals() else 'unknown',
                'duration': transcript_data[-1]['start'] + transcript_data[-1]['duration'] if transcript_data else 0
            }
            
        except TranscriptsDisabled:
            return {
                'success': False,
                'error': 'Captions are disabled for this video'
            }
        except NoTranscriptFound:
            return {
                'success': False,
                'error': 'No captions found for this video'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Caption extraction failed: {str(e)}'
            }
    
    def _transcribe_audio_method(self, url: str, video_info: Dict) -> Dict:
        """Download and transcribe audio from video"""
        temp_dir = tempfile.mkdtemp()
        audio_file = None
        
        try:
            # Download audio
            logger.info("Downloading audio from YouTube...")
            audio_file = self._download_audio(url, temp_dir)
            
            if not audio_file:
                return {
                    'success': False,
                    'error': 'Failed to download audio from video'
                }
            
            # Transcribe audio
            logger.info("Transcribing audio (this may take a few minutes)...")
            transcript = self._transcribe_audio_file(audio_file)
            
            if not transcript:
                return {
                    'success': False,
                    'error': 'Audio transcription failed - speech may be unclear or in another language'
                }
            
            return {
                'success': True,
                'transcript': transcript,
                'source_type': 'audio_transcription',
                'title': video_info.get('title', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'warning': 'Transcription from audio may be less accurate than captions'
            }
            
        except Exception as e:
            logger.error(f"Audio transcription error: {e}")
            return {
                'success': False,
                'error': f'Audio processing failed: {str(e)}'
            }
        finally:
            # Cleanup
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except:
                    pass
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
    
    def _download_audio(self, url: str, output_dir: str) -> Optional[str]:
        """Download audio from YouTube video"""
        try:
            output_path = os.path.join(output_dir, 'audio.%(ext)s')
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'no_color': True,
                'no_call_home': True,
                # Avoid downloading video, just audio
                'extract_audio': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                # Find the downloaded file
                audio_file = os.path.join(output_dir, 'audio.wav')
                
                if os.path.exists(audio_file):
                    return audio_file
                    
                # Check for other possible extensions
                for ext in ['m4a', 'mp3', 'webm', 'opus']:
                    alt_file = os.path.join(output_dir, f'audio.{ext}')
                    if os.path.exists(alt_file):
                        # Convert to WAV
                        audio = AudioSegment.from_file(alt_file)
                        audio.export(audio_file, format="wav")
                        os.remove(alt_file)
                        return audio_file
                        
                return None
                
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            return None
    
    def _transcribe_audio_file(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file using speech recognition"""
        try:
            # Load and prepare audio
            audio = AudioSegment.from_wav(audio_file)
            
            # Convert to proper format (16kHz, mono)
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Split into chunks (1 minute each for Google's free tier)
            chunk_length_ms = 60000
            chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
            
            logger.info(f"Processing {len(chunks)} audio chunks...")
            
            full_transcript = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Transcribing chunk {i+1}/{len(chunks)}...")
                
                # Export chunk
                chunk_file = f"{audio_file}_chunk_{i}.wav"
                chunk.export(chunk_file, format="wav")
                
                try:
                    with sr.AudioFile(chunk_file) as source:
                        audio_data = self.recognizer.record(source)
                        
                        try:
                            # Use Google's free speech recognition
                            text = self.recognizer.recognize_google(audio_data)
                            full_transcript.append(text)
                            logger.info(f"Chunk {i+1} transcribed successfully")
                        except sr.UnknownValueError:
                            logger.warning(f"Chunk {i+1}: No speech detected")
                        except sr.RequestError as e:
                            logger.error(f"Chunk {i+1}: API error: {e}")
                            # Don't fail entirely, continue with other chunks
                            
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}")
                finally:
                    # Clean up chunk file
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
            
            # Join all chunks
            final_transcript = ' '.join(full_transcript)
            
            if not final_transcript.strip():
                return None
                
            return self._clean_transcript_text(final_transcript)
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def _clean_transcript_text(self, text: str) -> str:
        """Clean up transcript text"""
        # Remove music/sound notations
        text = re.sub(r'\[(?:music|applause|laughter|inaudible)\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\((?:music|applause|laughter|inaudible)\)', '', text, flags=re.IGNORECASE)
        
        # Fix spacing
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Remove excess whitespace
        text = text.strip()
        
        return text
    
    def get_capabilities(self) -> Dict:
        """Return current capabilities of the YouTube service"""
        return {
            'supported': {
                'youtube_videos_with_captions': True,
                'youtube_videos_without_captions': 'Limited to 30 minutes',
                'youtube_shorts': True,
                'youtube_live_streams': False,
                'real_time_streaming': False
            },
            'limitations': {
                'audio_transcription_limit': '30 minutes',
                'live_stream_support': 'Not available - use recorded version after stream ends',
                'accuracy': 'Captions > Audio transcription',
                'api_rate_limits': 'Google Speech API has hourly limits'
            },
            'recommendations': {
                'best_results': 'Use videos with manual captions',
                'for_live_content': 'Use microphone feature to capture audio from speakers',
                'for_long_videos': 'Only videos with captions can exceed 30 minutes'
            }
        }
