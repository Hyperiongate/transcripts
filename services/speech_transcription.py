# services/speech_transcription.py
"""
Live speech-to-text transcription for streams without captions
"""
import asyncio
import aiohttp
from typing import AsyncGenerator, Dict
import numpy as np
from google.cloud import speech_v1
import azure.cognitiveservices.speech as speechsdk

class LiveSpeechTranscriber:
    """Transcribe live audio streams"""
    
    def __init__(self, provider='google'):
        self.provider = provider
        
        if provider == 'google':
            self.client = speech_v1.SpeechClient()
            self.config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
                enable_automatic_punctuation=True,
                enable_speaker_diarization=True,
                diarization_speaker_count=4,  # For debates
                model="video",  # Optimized for video content
            )
            self.streaming_config = speech_v1.StreamingRecognitionConfig(
                config=self.config,
                interim_results=True,
            )
            
        elif provider == 'azure':
            # Azure Speech Services setup
            speech_key = os.getenv("AZURE_SPEECH_KEY")
            service_region = os.getenv("AZURE_SPEECH_REGION")
            
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, 
                region=service_region
            )
            speech_config.speech_recognition_language = "en-US"
            self.speech_config = speech_config
    
    async def transcribe_stream(self, audio_stream_url: str) -> AsyncGenerator[Dict, None]:
        """Transcribe audio stream in real-time"""
        
        if self.provider == 'google':
            async for transcript in self._google_transcribe(audio_stream_url):
                yield transcript
        elif self.provider == 'azure':
            async for transcript in self._azure_transcribe(audio_stream_url):
                yield transcript
    
    async def _google_transcribe(self, audio_url: str) -> AsyncGenerator[Dict, None]:
        """Google Cloud Speech-to-Text streaming"""
        
        async def audio_generator():
            """Generate audio chunks from stream"""
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as response:
                    async for chunk in response.content.iter_chunked(4096):
                        yield speech_v1.StreamingRecognizeRequest(audio_content=chunk)
        
        # Start streaming recognition
        responses = self.client.streaming_recognize(
            self.streaming_config,
            audio_generator()
        )
        
        for response in responses:
            for result in response.results:
                if result.is_final:
                    # Get the best alternative
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    
                    # Extract speaker info if available
                    speaker_tag = None
                    if hasattr(result.alternatives[0], 'words'):
                        for word_info in result.alternatives[0].words:
                            if hasattr(word_info, 'speaker_tag'):
                                speaker_tag = word_info.speaker_tag
                                break
                    
                    yield {
                        'text': transcript,
                        'confidence': confidence,
                        'is_final': True,
                        'speaker': speaker_tag,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    # Interim result
                    yield {
                        'text': result.alternatives[0].transcript,
                        'confidence': None,
                        'is_final': False,
                        'timestamp': datetime.now().isoformat()
                    }

# Updated API endpoint for live transcription
@app.route('/api/transcribe-live', methods=['POST'])
async def transcribe_live():
    """Start live transcription of audio stream"""
    data = request.get_json()
    stream_url = data.get('stream_url')
    source = data.get('source', 'unknown')
    
    if not stream_url:
        return jsonify({'error': 'No stream URL provided'}), 400
    
    job_id = str(uuid.uuid4())
    
    # Initialize transcriber
    transcriber = LiveSpeechTranscriber(provider='google')
    
    # Start transcription in background
    async def process_transcripts():
        jobs[job_id] = {
            'id': job_id,
            'status': 'transcribing',
            'source': source,
            'segments': [],
            'claims_checked': 0
        }
        
        segment_buffer = []
        
        async for transcript in transcriber.transcribe_stream(stream_url):
            if transcript['is_final']:
                # Add to segment buffer
                segment_buffer.append(transcript)
                
                # Process every 5 segments or 30 seconds
                if len(segment_buffer) >= 5:
                    # Combine segments
                    combined_text = ' '.join([s['text'] for s in segment_buffer])
                    
                    # Extract and check claims
                    claims = claim_extractor.extract_claims(combined_text)
                    if claims:
                        prioritized = claim_extractor.prioritize_claims(claims)[:3]
                        fact_checks = fact_checker.batch_check(prioritized)
                        
                        # Update job
                        jobs[job_id]['segments'].append({
                            'text': combined_text,
                            'claims': len(claims),
                            'fact_checks': fact_checks,
                            'timestamp': transcript['timestamp']
                        })
                        
                        jobs[job_id]['claims_checked'] += len(fact_checks)
                    
                    # Clear buffer
                    segment_buffer = []
    
    # Start async task
    asyncio.create_task(process_transcripts())
    
    return jsonify({
        'success': True,
        'job_id': job_id,
        'message': 'Live transcription started'
    })
