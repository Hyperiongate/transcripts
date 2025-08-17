// Fact Checker Application JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const methodTabs = document.querySelectorAll('.method-tab');
    const inputPanels = document.querySelectorAll('.input-panel');
    
    methodTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const method = this.dataset.method;
            
            // Update active states
            methodTabs.forEach(t => t.classList.remove('active'));
            inputPanels.forEach(p => p.classList.remove('active'));
            
            this.classList.add('active');
            document.getElementById(`${method}-panel`).classList.add('active');
        });
    });
    
    // File upload
    const fileInput = document.getElementById('file-input');
    const fileUploadArea = document.querySelector('.file-upload-area');
    
    if (fileUploadArea) {
        fileUploadArea.addEventListener('click', () => fileInput.click());
        
        fileUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileUploadArea.classList.add('dragover');
        });
        
        fileUploadArea.addEventListener('dragleave', () => {
            fileUploadArea.classList.remove('dragover');
        });
        
        fileUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            fileUploadArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                updateFileInfo(e.dataTransfer.files[0]);
            }
        });
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                updateFileInfo(e.target.files[0]);
            }
        });
    }
    
    // Form submission
    const form = document.getElementById('fact-check-form');
    form.addEventListener('submit', handleSubmit);
});

function updateFileInfo(file) {
    const fileInfo = document.querySelector('.file-info');
    if (fileInfo) {
        fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function handleSubmit(e) {
    e.preventDefault();
    
    // Get the active input method
    const activePanel = document.querySelector('.input-panel.active');
    const method = activePanel.id.replace('-panel', '');
    
    let transcript = '';
    let source = '';
    
    try {
        // Get transcript based on method
        if (method === 'text') {
            transcript = document.getElementById('transcript-text').value.trim();
            source = 'Direct Input';
            
            if (!transcript) {
                showError('Please enter a transcript to analyze');
                return;
            }
        } else if (method === 'file') {
            const fileInput = document.getElementById('file-input');
            if (!fileInput.files || fileInput.files.length === 0) {
                showError('Please select a file to analyze');
                return;
            }
            
            const file = fileInput.files[0];
            transcript = await readFile(file);
            source = `File: ${file.name}`;
        } else if (method === 'youtube') {
            const url = document.getElementById('youtube-url').value.trim();
            if (!url) {
                showError('Please enter a YouTube URL');
                return;
            }
            
            // For YouTube, send the URL as the transcript
            transcript = url;
            source = `YouTube: ${url}`;
        }
        
        // Validate transcript
        if (!transcript || transcript.length < 50) {
            showError('Transcript is too short. Please provide more content to analyze.');
            return;
        }
        
        // Send to API
        await analyzeTranscript(transcript, source);
        
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while processing your request');
    }
}

async function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

async function analyzeTranscript(transcript, source) {
    // Show progress section
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('results-section').classList.add('hidden');
    
    // Reset progress
    updateProgress(0, 'Initializing analysis...');
    
    try {
        // Send analysis request
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transcript: transcript,
                source: source
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Analysis failed');
        }
        
        if (!data.success) {
            throw new Error(data.error || 'Analysis failed');
        }
        
        // Start polling for results
        const jobId = data.job_id;
        pollJobStatus(jobId);
        
    } catch (error) {
        console.error('Analysis error:', error);
        showError(error.message || 'Failed to analyze transcript');
        document.getElementById('progress-section').classList.add('hidden');
    }
}

async function pollJobStatus(jobId) {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;
    
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${jobId}`);
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                throw new Error('Failed to get job status');
            }
            
            // Update progress
            updateProgress(data.progress || 0, getProgressText(data.progress));
            
            if (data.status === 'completed') {
                clearInterval(interval);
                await loadResults(jobId);
            } else if (data.status === 'failed') {
                clearInterval(interval);
                throw new Error(data.error || 'Analysis failed');
            }
            
            attempts++;
            if (attempts >= maxAttempts) {
                clearInterval(interval);
                throw new Error('Analysis timed out');
            }
            
        } catch (error) {
            clearInterval(interval);
            console.error('Polling error:', error);
            showError(error.message || 'Failed to get analysis status');
            document.getElementById('progress-section').classList.add('hidden');
        }
    }, 5000); // Poll every 5 seconds
}

function updateProgress(percent, text) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressFill.style.width = percent + '%';
    progressText.textContent = text;
}

function getProgressText(progress) {
    if (progress < 20) return 'Processing transcript...';
    if (progress < 40) return 'Extracting claims...';
    if (progress < 60) return 'Fact-checking claims...';
    if (progress < 80) return 'Analyzing credibility...';
    if (progress < 100) return 'Finalizing results...';
    return 'Analysis complete!';
}

async function loadResults(jobId) {
    try {
        const response = await fetch(`/api/results/${jobId}`);
        const results = await response.json();
        
        if (!response.ok || !results.success) {
            throw new Error('Failed to load results');
        }
        
        // Display results
        displayResults(results);
        
        // Show results section
        document.getElementById('progress-section').classList.add('hidden');
        document.getElementById('results-section').classList.remove('hidden');
        
        // Set up export buttons
        setupExportButtons(jobId);
        
    } catch (error) {
        console.error('Results error:', error);
        showError('Failed to load analysis results');
    }
}

function displayResults(results) {
    // Update credibility score
    const score = results.credibility_score || 0;
    document.getElementById('credibility-meter').style.width = score + '%';
    document.getElementById('credibility-score').textContent = score + '%';
    document.getElementById('credibility-label').textContent = results.credibility_label || 'Unknown';
    
    // Update stats
    updateStats(results);
    
    // Display summary
    const summaryContainer = document.getElementById('analysis-summary');
    if (results.speaker_context && results.speaker_context.speaker) {
        const context = results.speaker_context;
        
        let summaryHtml = '<div class="speaker-context-section">';
        summaryHtml += `<h4>About ${context.speaker}:</h4>`;
        
        if (context.criminal_record) {
            summaryHtml += `<div class="alert alert-danger">
                <strong>⚖️ Criminal Record:</strong> ${context.criminal_record}
            </div>`;
        }
        
        if (context.fraud_history) {
            summaryHtml += `<div class="alert alert-warning">
                <strong>💰 Fraud History:</strong> ${context.fraud_history}
            </div>`;
        }
        
        summaryHtml += '</div>';
        summaryContainer.innerHTML = summaryHtml;
    }
    
    if (results.conversational_summary) {
        summaryContainer.innerHTML += `<div class="conversational-summary">
            <h4>Summary:</h4>
            <p>${results.conversational_summary}</p>
        </div>`;
    }
    
    // Display fact checks
    if (window.displayEnhancedFactChecks) {
        window.updateEnhancedStats(results);
        window.displayEnhancedFactChecks(results.fact_checks || []);
    } else {
        displayFactChecks(results.fact_checks || []);
    }
}

function updateStats(results) {
    let verifiedCount = 0;
    let falseCount = 0;
    let unverifiedCount = 0;
    
    if (results.fact_checks && Array.isArray(results.fact_checks)) {
        results.fact_checks.forEach(check => {
            const verdict = (check.verdict || 'unverified').toLowerCase();
            if (verdict === 'true' || verdict === 'mostly_true') {
                verifiedCount++;
            } else if (verdict === 'false' || verdict === 'mostly_false') {
                falseCount++;
            } else {
                unverifiedCount++;
            }
        });
    }
    
    document.getElementById('verified-claims').textContent = verifiedCount;
    document.getElementById('false-claims').textContent = falseCount;
    document.getElementById('unverified-claims').textContent = unverifiedCount;
}

function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    if (!factChecks || factChecks.length === 0) {
        container.innerHTML = '<p>No fact checks available.</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        item.className = 'fact-check-item';
        
        const verdict = check.verdict || 'unverified';
        const verdictClass = getVerdictClass(verdict);
        
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-claim">${check.claim}</div>
                <div class="fact-check-verdict ${verdictClass}">${verdict}</div>
            </div>
            <div class="fact-check-details">
                <p>${check.explanation || 'No explanation available'}</p>
                <div class="fact-check-meta">
                    <span>Confidence: ${check.confidence || 0}%</span>
                    <span>Source: ${check.source || 'Unknown'}</span>
                </div>
            </div>
        `;
        
        container.appendChild(item);
    });
}

function getVerdictClass(verdict) {
    const verdictLower = verdict.toLowerCase();
    if (verdictLower === 'true' || verdictLower === 'mostly_true') return 'verdict-true';
    if (verdictLower === 'false' || verdictLower === 'mostly_false') return 'verdict-false';
    if (verdictLower === 'mixed') return 'verdict-mixed';
    return 'verdict-unverified';
}

function setupExportButtons(jobId) {
    const exportButtons = document.querySelectorAll('.export-btn');
    exportButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const format = this.dataset.format;
            window.location.href = `/api/export/${jobId}/${format}`;
        });
    });
}

function showError(message) {
    // Simple alert for now - you can make this prettier
    alert('Error: ' + message);
}

// Make displayResults available globally for enhanced.js
window.displayResults = displayResults;
