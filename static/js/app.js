// Main application JavaScript
// Note: VERDICT_MAPPINGS is already defined in enhanced.js

// Global variables
let currentJobId = null;
let pollInterval = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tabs
    const tabButtons = document.querySelectorAll('.tab-button');
    const panels = document.querySelectorAll('.input-panel');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            // Update active states
            tabButtons.forEach(btn => btn.classList.remove('active'));
            panels.forEach(panel => panel.classList.remove('active'));
            
            button.classList.add('active');
            document.getElementById(`${targetTab}-panel`).classList.add('active');
        });
    });
    
    // Character counter
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    if (textInput) {
        textInput.addEventListener('input', () => {
            charCount.textContent = textInput.value.length;
            
            // Warn if approaching limit
            if (textInput.value.length > 45000) {
                charCount.style.color = '#ef4444';
            } else {
                charCount.style.color = '#6b7280';
            }
        });
    }
    
    // File upload handling
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('file-drop-zone');
    
    if (dropZone) {
        dropZone.addEventListener('click', () => fileInput.click());
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }
});

// File handling
function handleFileSelect(file) {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['.txt', '.srt', '.vtt'];
    const fileExt = file.name.toLowerCase().substr(file.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExt)) {
        showError('Invalid file type. Please upload TXT, SRT, or VTT files.');
        return;
    }
    
    if (file.size > maxSize) {
        showError('File too large. Maximum size is 10MB.');
        return;
    }
    
    // Show file info
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-info').style.display = 'flex';
    document.getElementById('file-drop-zone').style.display = 'none';
}

function removeFile() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-drop-zone').style.display = 'block';
}

// Start analysis
async function startAnalysis() {
    const activePanel = document.querySelector('.input-panel.active').id;
    const isTextInput = activePanel === 'text-panel';
    
    let transcript = '';
    
    if (isTextInput) {
        transcript = document.getElementById('text-input').value.trim();
        if (!transcript) {
            showError('Please enter a transcript to analyze.');
            return;
        }
        if (transcript.length > 50000) {
            showError('Transcript too long. Maximum 50,000 characters.');
            return;
        }
    } else {
        const fileInput = document.getElementById('file-input');
        if (!fileInput.files || fileInput.files.length === 0) {
            showError('Please select a file to analyze.');
            return;
        }
        
        // Read file content
        const file = fileInput.files[0];
        try {
            transcript = await readFileContent(file);
        } catch (error) {
            showError('Error reading file: ' + error.message);
            return;
        }
    }
    
    // Hide input section, show progress
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    
    // Submit for analysis
    submitTranscript(transcript);
}

// Read file content
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

// Submit transcript to API
async function submitTranscript(transcript) {
    try {
        updateProgress(10, 'Submitting transcript...');
        
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ transcript: transcript })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentJobId = data.job_id;
            pollForResults();
        } else {
            throw new Error(data.error || 'Failed to submit transcript');
        }
    } catch (error) {
        showError('Error: ' + error.message);
        resetAnalysis();
    }
}

// Poll for results
function pollForResults() {
    let attempts = 0;
    const maxAttempts = 60; // 1 minute timeout
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const data = await response.json();
            
            if (response.ok) {
                // Update progress
                const progress = data.progress || 0;
                const message = data.message || 'Processing...';
                updateProgress(progress, message);
                
                // Update steps
                if (progress >= 25) document.getElementById('step-1').classList.add('active');
                if (progress >= 50) document.getElementById('step-2').classList.add('active');
                if (progress >= 75) document.getElementById('step-3').classList.add('active');
                if (progress >= 90) document.getElementById('step-4').classList.add('active');
                
                // Check if completed
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    getResults();
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    showError(data.error || 'Analysis failed');
                    resetAnalysis();
                }
            }
            
            attempts++;
            if (attempts >= maxAttempts) {
                clearInterval(pollInterval);
                showError('Analysis timeout. Please try again.');
                resetAnalysis();
            }
        } catch (error) {
            clearInterval(pollInterval);
            showError('Connection error. Please try again.');
            resetAnalysis();
        }
    }, 1000);
}

// Get results
async function getResults() {
    try {
        const response = await fetch(`/api/results/${currentJobId}`);
        const results = await response.json();
        
        if (response.ok) {
            displayResults(results);
        } else {
            throw new Error(results.error || 'Failed to get results');
        }
    } catch (error) {
        showError('Error getting results: ' + error.message);
        resetAnalysis();
    }
}

// Update progress
function updateProgress(percent, message) {
    document.getElementById('progress-fill').style.width = percent + '%';
    document.getElementById('progress-text').textContent = message;
}

// Display results
function displayResults(results) {
    // Hide progress, show results
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    // Update credibility score
    const score = results.credibility_score?.score || 0;
    const label = results.credibility_score?.label || 'Unknown';
    
    document.getElementById('credibility-value').textContent = score;
    document.getElementById('credibility-label').textContent = label;
    
    // Position meter pointer
    const pointer = document.getElementById('credibility-pointer');
    pointer.style.left = `calc(${score}% - 3px)`;
    
    // Update summary
    const summary = results.conversational_summary || results.summary || 'No summary available.';
    document.getElementById('analysis-summary').innerHTML = formatSummary(summary);
    
    // Update stats
    document.getElementById('total-claims').textContent = results.total_claims || 0;
    document.getElementById('verified-claims').textContent = 
        results.credibility_score?.breakdown?.accurate || 0;
    document.getElementById('false-claims').textContent = 
        results.credibility_score?.breakdown?.false || 0;
    document.getElementById('unverified-claims').textContent = 
        results.credibility_score?.breakdown?.other || 0;
    
    // Display fact checks
    displayFactChecks(results.fact_checks || []);
    
    // Add speaker/topic info if available
    if (results.speakers && results.speakers.length > 0) {
        const speakerInfo = document.createElement('div');
        speakerInfo.className = 'speaker-info';
        speakerInfo.innerHTML = `<strong>Speakers:</strong> ${results.speakers.join(', ')}`;
        document.getElementById('analysis-summary').appendChild(speakerInfo);
    }
    
    if (results.topics && results.topics.length > 0) {
        const topicInfo = document.createElement('div');
        topicInfo.className = 'topic-info';
        topicInfo.innerHTML = `<strong>Topics:</strong> ${results.topics.join(', ')}`;
        document.getElementById('analysis-summary').appendChild(topicInfo);
    }
}

// Format summary text
function formatSummary(summary) {
    return summary
        .replace(/\n/g, '<br>')
        .replace(/✅/g, '<span style="color: #10b981;">✅</span>')
        .replace(/❌/g, '<span style="color: #ef4444;">❌</span>')
        .replace(/⚠️/g, '<span style="color: #f59e0b;">⚠️</span>')
        .replace(/🚨/g, '<span style="color: #dc2626;">🚨</span>')
        .replace(/💡/g, '<span style="color: #3b82f6;">💡</span>');
}

// Display fact checks
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280;">No fact checks available.</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        const verdict = check.verdict || 'unverified';
        const verdictClass = getVerdictClass(verdict);
        
        item.className = `fact-check-item ${verdictClass}`;
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-claim">${check.claim || 'No claim text'}</div>
                <div class="fact-check-verdict ${verdictClass}">
                    <i class="fas ${getVerdictIcon(verdict)}"></i>
                    ${formatVerdict(verdict)}
                </div>
            </div>
            <div class="fact-check-details">
                <p>${check.explanation || 'No explanation available.'}</p>
                ${check.sources && check.sources.length > 0 ? 
                    `<div class="fact-check-source">
                        <strong>Sources:</strong> ${check.sources.join(', ')}
                    </div>` : ''}
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Get verdict class
function getVerdictClass(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    
    if (VERDICT_MAPPINGS && VERDICT_MAPPINGS[v]) {
        return VERDICT_MAPPINGS[v].class;
    }
    
    // Fallback mapping
    const mapping = {
        'true': 'true',
        'mostly_true': 'true',
        'nearly_true': 'true',
        'false': 'false',
        'mostly_false': 'false',
        'misleading': 'false',
        'intentionally_deceptive': 'false',
        'exaggeration': 'unverified',
        'needs_context': 'unverified',
        'opinion': 'unverified',
        'unverified': 'unverified'
    };
    
    return mapping[v] || 'unverified';
}

// Get verdict icon
function getVerdictIcon(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    
    if (VERDICT_MAPPINGS && VERDICT_MAPPINGS[v]) {
        return VERDICT_MAPPINGS[v].icon;
    }
    
    // Fallback icons
    const icons = {
        'true': 'fa-check-circle',
        'mostly_true': 'fa-check-circle',
        'nearly_true': 'fa-check-circle',
        'false': 'fa-times-circle',
        'mostly_false': 'fa-times-circle',
        'misleading': 'fa-exclamation-triangle',
        'intentionally_deceptive': 'fa-exclamation-triangle',
        'exaggeration': 'fa-question-circle',
        'needs_context': 'fa-question-circle',
        'opinion': 'fa-comment',
        'unverified': 'fa-question-circle'
    };
    
    return icons[v] || 'fa-question-circle';
}

// Format verdict label
function formatVerdict(verdict) {
    if (VERDICT_MAPPINGS && VERDICT_MAPPINGS[verdict]) {
        return VERDICT_MAPPINGS[verdict].label;
    }
    
    // Fallback formatting
    return verdict.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Export results
async function exportResults(format) {
    if (!currentJobId) {
        showError('No results to export');
        return;
    }
    
    try {
        window.location.href = `/api/export/${currentJobId}`;
    } catch (error) {
        showError('Error exporting results: ' + error.message);
    }
}

// Reset analysis
function resetAnalysis() {
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    
    // Reset progress
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Initializing...';
    
    // Reset steps
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    
    // Clear job ID
    currentJobId = null;
    
    // Clear poll interval
    if (pollInterval) {
        clearInterval(pollInterval);
    }
}

// Show error message
function showError(message) {
    alert(message); // Simple alert for now
    // TODO: Implement better error display
}
