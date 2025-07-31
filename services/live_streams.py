# services/live_streams.py
"""
Live stream transcript extraction from multiple sources
"""
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import webvtt
import m3u8
from datetime import datetime

class StreamSource(ABC):
    """Base class for stream sources"""
    
    @abstractmethod
    async def get_captions_url(self, stream_url: str) -> Optional[str]:
        """Extract caption URL from stream"""
        pass
    
    @abstractmethod
    async def fetch_captions(self, caption_url: str) -> List[Dict]:
        """Fetch latest captions"""
        pass

class ABCNewsSource(StreamSource):
    """ABC News Live stream handler"""
    
    async def get_captions_url(self, stream_url: str) -> Optional[str]:
        """Extract caption track from ABC News stream"""
        # ABC News typically uses HLS streams with WebVTT captions
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url) as response:
                content = await response.text()
                
                # Parse m3u8 playlist
                playlist = m3u8.loads(content)
                
                # Look for subtitle tracks
                for media in playlist.media:
                    if media.type == "SUBTITLES":
                        return media.absolute_uri
                        
        return None
    
    async def fetch_captions(self, caption_url: str) -> List[Dict]:
        """Fetch WebVTT captions"""
        async with aiohttp.ClientSession() as session:
            async with session.get(caption_url) as response:
                vtt_content = await response.text()
                
                # Parse WebVTT
                captions = []
                for caption in webvtt.read_buffer(vtt_content):
                    captions.append({
                        'start': caption.start_in_seconds,
                        'end': caption.end_in_seconds,
                        'text': caption.text
                    })
                
                return captions

class PBSNewsSource(StreamSource):
    """PBS NewsHour stream handler"""
    
    async def get_captions_url(self, stream_url: str) -> Optional[str]:
        """PBS often provides direct caption URLs"""
        # Implementation for PBS streams
        pass
    
    async def fetch_captions(self, caption_url: str) -> List[Dict]:
        """Fetch PBS captions"""
        pass

class LiveTranscriptAggregator:
    """Aggregate transcripts from multiple sources"""
    
    def __init__(self):
        self.sources = {
            'abc': ABCNewsSource(),
            'pbs': PBSNewsSource(),
            # Add more sources
        }
        self.active_streams = {}
        
    async def start_monitoring(self, source_name: str, stream_url: str, callback):
        """Start monitoring a live stream"""
        if source_name not in self.sources:
            raise ValueError(f"Unknown source: {source_name}")
            
        source = self.sources[source_name]
        
        # Get caption URL
        caption_url = await source.get_captions_url(stream_url)
        if not caption_url:
            raise ValueError("No captions found for this stream")
            
        # Start monitoring loop
        stream_id = f"{source_name}_{datetime.now().timestamp()}"
        self.active_streams[stream_id] = True
        
        last_caption_time = 0
        
        while self.active_streams.get(stream_id, False):
            try:
                # Fetch latest captions
                captions = await source.fetch_captions(caption_url)
                
                # Find new captions
                new_captions = [
                    c for c in captions 
                    if c['start'] > last_caption_time
                ]
                
                if new_captions:
                    last_caption_time = new_captions[-1]['start']
                    
                    # Aggregate text
                    text_chunk = ' '.join([c['text'] for c in new_captions])
                    
                    # Send to callback
                    await callback({
                        'source': source_name,
                        'text': text_chunk,
                        'captions': new_captions,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Wait before next check
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Error in stream monitoring: {e}")
                await asyncio.sleep(30)  # Longer wait on error
                
        return stream_id
    
    def stop_monitoring(self, stream_id: str):
        """Stop monitoring a stream"""
        self.active_streams[stream_id] = False
