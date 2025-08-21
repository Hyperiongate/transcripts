"""
Transcript Processing Service
Handles cleaning and preprocessing of transcripts from various sources
"""
import re
import logging
import os
from typing import List, Dict, Optional
import PyPDF2
import docx
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process and clean transcripts from various sources"""
    
    def __init__(self):
        pass
    
    def process(self, input_text: str) -> str:
        """Process input text and return clean transcript"""
        # Treat all input as direct transcript
        return self.clean_transcript(input_text)
    
    def process_file(self, filepath: str) -> str:
        """Process uploaded file and extract transcript"""
        file_extension = filepath.lower().split('.')[-1]
        
        try:
            if file_extension == 'txt':
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            elif file_extension == 'pdf':
                content = self._extract_pdf_text(filepath)
            
            elif file_extension in ['docx', 'doc']:
                content = self._extract_docx_text(filepath)
            
            elif file_extension in ['srt', 'vtt']:
                content = self._extract_subtitle_text(filepath)
            
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            return self.clean_transcript(content)
            
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {str(e)}")
            raise
    
    def process_youtube(self, url: str) -> str:
        """Extract transcript from YouTube video"""
        try:
            # Extract video ID from URL
            video_id = self._extract_youtube_id(url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")
            
            # Get transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine transcript entries
            text_parts = []
            for entry in transcript_list:
                text_parts.append(entry['text'])
            
            full_text = ' '.join(text_parts)
            return self.clean_transcript(full_text)
            
        except Exception as e:
            logger.error(f"Error extracting YouTube transcript: {str(e)}")
            raise ValueError(f"Could not extract transcript from YouTube video: {str(e)}")
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
            r'(?:youtu\.be\/)([\w-]+)',
            r'(?:youtube\.com\/v\/)([\w-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_pdf_text(self, filepath: str) -> str:
        """Extract text from PDF file"""
        text_parts = []
        
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_parts.append(page.extract_text())
        
        return '\n'.join(text_parts)
    
    def _extract_docx_text(self, filepath: str) -> str:
        """Extract text from DOCX file"""
        doc = docx.Document(filepath)
        text_parts = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return '\n'.join(text_parts)
    
    def _extract_subtitle_text(self, filepath: str) -> str:
        """Extract text from subtitle files (SRT/VTT)"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove subtitle formatting
        # Remove timestamps
        content = re.sub(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', '', content)
        # Remove subtitle numbers
        content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)
        # Remove VTT header
        content = re.sub(r'^WEBVTT.*$', '', content, flags=re.MULTILINE)
        
        # Clean up extra newlines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content
    
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
