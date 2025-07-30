# Transcript Fact Checker

A focused web application for fact-checking transcripts from speeches, interviews, and YouTube videos using AI-powered claim extraction and Google's Fact Check API.

## Features

- 📝 **Multiple Input Methods**: Direct text, file upload (TXT/SRT/VTT), YouTube URLs
- 🔍 **Smart Claim Extraction**: AI-powered identification of factual claims
- ✅ **Fact Verification**: Integration with Google Fact Check API
- 📊 **Credibility Scoring**: Visual credibility meter and detailed analysis
- 📥 **Export Options**: Download results as JSON, TXT, or PDF
- 🎯 **Real-time Progress**: Track analysis progress step-by-step

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/transcript-factchecker.git
   cd transcript-factchecker
   ```

2. **Set up environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure API keys**
   ```bash
   cp .env.example .env
   # Edit .env and add your Google Fact Check API key
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5000
   ```

### Docker Deployment

```bash
docker build -t transcript-factchecker .
docker run -p 5000:5000 --env-file .env transcript-factchecker
```

## API Keys

To use the Google Fact Check API:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable "Fact Check Tools API"
4. Create credentials (API Key)
5. Add to your `.env` file

## Usage

1. **Choose Input Method**: Text, File Upload, or YouTube URL
2. **Submit Content**: Click "Analyze Transcript"
3. **View Results**: See credibility score and fact-check details
4. **Export**: Download results in your preferred format

## Technology Stack

- **Backend**: Flask, Python 3.11
- **NLP**: spaCy, NLTK
- **APIs**: Google Fact Check, YouTube Transcript
- **Frontend**: Vanilla JavaScript, CSS3
- **Deployment**: Docker, Gunicorn

## File Structure

```
transcript-factchecker/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── services/            # Core processing modules
│   ├── transcript.py    # Transcript processing
│   ├── claims.py        # Claim extraction
│   └── factcheck.py     # Fact verification
├── static/              # Frontend assets
│   ├── css/
│   └── js/
└── templates/           # HTML templates
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License - feel free to use this project for your own purposes.
