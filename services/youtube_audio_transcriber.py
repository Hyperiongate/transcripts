"""
YouTube Audio Transcriber - Simple version using SpeechRecognition
This is a new file - create it as: services/youtube_audio_transcriber.py
"""
import os
import tempfile
import logging
from typing import Dict, Optional
import yt_dlp
import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class YouTubeAudioTranscriber:
    """Transcribe audio from YouTube videos"""
    
    def __init__(self):
        """Initialize speech recognizer"""
        self.recognizer = sr.Recognizer()
        logger.info("Initialized YouTube audio transcriber")
    
    def transcribe_youtube_video(self, url: str) -> Dict:
        """
        Download and transcribe audio from YouTube video
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dict with transcript and metadata
        """
        temp_dir = tempfile.mkdtemp()
        audio_file = None
        
        try:
            # Step 1: Download audio from YouTube
            logger.info(f"Downloading audio from: {url}")
            audio_file, video_info = self._download_audio(url, temp_dir)
            
            if not audio_file:
                return {
                    'success': False,
                    'error': 'Failed to download audio from video'
                }
            
            # Check video duration (limit to 30 minutes for free tier)
            duration = video_info.get('duration', 0)
            if duration > 1800:  # 30 minutes
                return {
                    'success': False,
                    'error': 'Video is too long. Maximum 30 minutes for audio transcription.'
                }
            
            # Step 2: Transcribe the audio
            logger.info("Transcribing audio using Google Speech Recognition")
            transcript = self._transcribe_audio(audio_file)
            
            if not transcript:
                return {
                    'success': False,
                    'error': 'Failed to transcribe audio. The speech might be unclear or in a different language.'
                }
            
            # Step 3: Return results
            return {
                'success': True,
                'transcript': transcript,
                'title': video_info.get('title', 'Unknown'),
                'duration': duration,
                'video_id': video_info.get('id', ''),
                'source_type': 'audio_transcription',
                'language': 'en'
            }
            
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            return {
                'success': False,
                'error': f'Transcription failed: {str(e)}'
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
    
    def _download_audio(self, url: str, output_dir: str) -> tuple[Optional[str], Dict]:
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
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Find the downloaded file
                audio_file = os.path.join(output_dir, 'audio.wav')
                
                if os.path.exists(audio_file):
                    return audio_file, info
                else:
                    # Try other extensions
                    for ext in ['m4a', 'mp3', 'webm', 'opus']:
                        alt_file = os.path.join(output_dir, f'audio.{ext}')
                        if os.path.exists(alt_file):
                            # Convert to WAV for speech recognition
                            audio = AudioSegment.from_file(alt_file)
                            audio.export(audio_file, format="wav")
                            os.remove(alt_file)
                            return audio_file, info
                    
                    logger.error("Audio file not found after download")
                    return None, {}
                    
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return None, {}
    
    def _transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file using Google Speech Recognition"""
        try:
            # Load audio
            audio = AudioSegment.from_wav(audio_file)
            
            # Convert to proper format (16kHz, mono)
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Split into 1-minute chunks (Google's free tier limit)
            chunk_length_ms = 60000  # 1 minute
            chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
            
            logger.info(f"Split audio into {len(chunks)} chunks")
            
            full_transcript = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Transcribing chunk {i+1}/{len(chunks)}")
                
                # Export chunk to temporary file
                chunk_file = f"{audio_file}_chunk_{i}.wav"
                chunk.export(chunk_file, format="wav")
                
                try:
                    # Transcribe chunk
                    with sr.AudioFile(chunk_file) as source:
                        audio_data = self.recognizer.record(source)
                        
                        # Try Google Speech Recognition (free)
                        try:
                            text = self.recognizer.recognize_google(audio_data)
                            full_transcript.append(text)
                            logger.info(f"Chunk {i+1} transcribed successfully")
                        except sr.UnknownValueError:
                            logger.warning(f"Chunk {i+1}: Speech not recognized")
                        except sr.RequestError as e:
                            logger.error(f"Chunk {i+1}: Google Speech API error: {e}")
                            
                except Exception as e:
                    logger.error(f"Error transcribing chunk {i+1}: {str(e)}")
                finally:
                    # Clean up chunk file
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
            
            # Join all chunks
            final_transcript = ' '.join(full_transcript)
            
            if not final_transcript.strip():
                return None
                
            return final_transcript.strip()
            
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            return None
          
