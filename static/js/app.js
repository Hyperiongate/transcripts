// Main application JavaScript
// Complete version with all functionality

// Verdict mappings for new system
const VERDICT_MAPPINGS = {
    'verified_true': {
        label: 'Verified True',
        class: 'true',
        icon: 'fa-check-circle',
        color: '#10b981'
    },
    'verified_false': {
        label: 'Verified False',
        class: 'false',
        icon: 'fa-times-circle',
        color: '#ef4444'
    },
    'partially_accurate': {
        label: 'Partially Accurate',
        class: 'mixed',
        icon: 'fa-exclamation-triangle',
        color: '#f59e0b'
    },
    'unverifiable': {
        label: 'Unverifiable',
        class: 'unverified',
        icon: 'fa-question-circle',
        color: '#6b7280'
    },
    'opinion': {
        label: 'Opinion',
        class: 'opinion',
        icon: 'fa-comment',
        color: '#8b5cf6'
    },
    // Legacy verdict mappings for compatibility
    'true': {
        label: 'True',
        class: 'true',
        icon: 'fa-check-circle',
        color: '#10b981'
    },
    'false': {
        label: 'False',
        class: 'false',
        icon: 'fa-times-circle',
        color: '#ef4444'
    },
    'mostly_true': {
        label: 'Mostly True',
        class: 'true',
        icon: 'fa-check-circle',
        color: '#34d399'
    },
    'mostly_false': {
        label: 'Mostly False',
        class: 'false',
        icon: 'fa-times-circle',
        color: '#f87171'
    },
    'misleading': {
        label: 'Misleading',
        class: 'mixed',
        icon: 'fa-exclamation-triangle',
        color: '#f59e0b'
    },
    'needs_context': {
        label: 'Needs Context',
        class: 'unverified',
        icon: 'fa-question-circle',
        color: '#6b7280'
    }
};

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
        
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ transcript })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to start analysis');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        pollJobStatus();
        
    } catch (error) {
        showError('Error: ' + error.message);
        resetAnalysis();
    }
}

// Poll job status
function pollJobStatus() {
    let pollCount = 0;
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const data = await response.json();
            
            if (response.ok) {
                console.log('Status:', data); // Debug log
                
                // Update progress if still processing
                if (data.progress && data.status === 'processing') {
                    updateProgress(data.progress, data.message);
                }
                
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    // Add a small delay to ensure server has saved results
                    setTimeout(() => {
                        getResults();
                    }, 100);
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    showError(data.error || 'Analysis failed');
                    resetAnalysis();
                }
            } else {
                clearInterval(pollInterval);
                showError('Error checking status. Please try again.');
                resetAnalysis();
            }
            
            // Timeout after 60 seconds
            pollCount++;
            if (pollCount > 60) {
                clearInterval(pollInterval);
                showError('Analysis timed out. Please try again.');
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
            console.log('Results received:', results); // Debug log
            displayResults(results);
        } else {
            throw new Error(results.error || 'Failed to get results');
        }
    } catch (error) {
        console.error('Error getting results:', error); // Debug log
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
    document.getElementById('summary-text').innerHTML = summary.replace(/\n/g, '<br>');
    
    // Update statistics
    const breakdown = results.credibility_score?.breakdown || {};
    document.getElementById('verified-true-count').textContent = breakdown.verified_true || 0;
    document.getElementById('verified-false-count').textContent = breakdown.verified_false || 0;
    document.getElementById('partially-accurate-count').textContent = breakdown.partially_accurate || 0;
    document.getElementById('unverifiable-count').textContent = breakdown.unverifiable || 0;
    
    // Display fact checks
    displayFactChecks(results.fact_checks || []);
    
    // Display speaker analysis if available
    if (results.speaker_analysis && Object.keys(results.speaker_analysis).length > 0) {
        displaySpeakerAnalysis(results.speaker_analysis);
    }
}

// Display fact checks
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-checks-container');
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p class="no-claims" style="text-align: center; color: #6b7280; padding: 40px;">No claims found to fact-check.</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        item.className = `fact-check-item verdict-${getVerdictClass(check.verdict)}`;
        
        const verdictInfo = VERDICT_MAPPINGS[check.verdict] || VERDICT_MAPPINGS['unverifiable'];
        
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-number">#${index + 1}</div>
                <div class="fact-check-verdict">
                    <i class="fas ${verdictInfo.icon}"></i>
                    ${verdictInfo.label}
                </div>
                ${check.speaker && check.speaker !== 'Unknown' ? `<div class="fact-check-speaker">${check.speaker}</div>` : ''}
            </div>
            <div class="fact-check-content">
                <p class="fact-check-claim">"${escapeHtml(check.claim || check.text || '')}"</p>
                <p class="fact-check-explanation">${escapeHtml(check.explanation || 'No explanation available.')}</p>
                ${check.confidence ? `<p class="fact-check-confidence">Confidence: ${check.confidence}%</p>` : ''}
                ${check.sources && check.sources.length > 0 ? 
                    `<div class="fact-check-source">
                        <strong>Sources:</strong> ${check.sources.map(s => escapeHtml(s)).join(', ')}
                    </div>` : ''}
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Display speaker analysis
function displaySpeakerAnalysis(speakerAnalysis) {
    const container = document.getElementById('speaker-analysis-container');
    if (!container) return;
    
    container.innerHTML = '<h4 style="margin-bottom: 20px;">Speaker Analysis</h4>';
    
    Object.entries(speakerAnalysis).forEach(([speaker, stats]) => {
        const speakerDiv = document.createElement('div');
        speakerDiv.className = 'speaker-stats';
        speakerDiv.style.cssText = 'background: #f3f4f6; padding: 20px; border-radius: 12px; margin-bottom: 16px;';
        
        const accuracy = stats.accuracy_rate !== null && stats.accuracy_rate !== undefined 
            ? `${stats.accuracy_rate}%` 
            : 'N/A';
        
        speakerDiv.innerHTML = `
            <h5 style="margin-bottom: 16px; font-size: 18px; font-weight: 600;">${escapeHtml(speaker)}</h5>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px;">
                <div class="stat">
                    <span style="display: block; color: #6b7280; font-size: 14px;">Total Claims:</span>
                    <span style="display: block; font-size: 20px; font-weight: 600;">${stats.total_claims || 0}</span>
                </div>
                <div class="stat">
                    <span style="display: block; color: #6b7280; font-size: 14px;">Accuracy Rate:</span>
                    <span style="display: block; font-size: 20px; font-weight: 600;">${accuracy}</span>
                </div>
                <div class="stat">
                    <span style="display: block; color: #6b7280; font-size: 14px;">Verified True:</span>
                    <span style="display: block; font-size: 20px; font-weight: 600; color: #10b981;">${stats.verified_true || 0}</span>
                </div>
                <div class="stat">
                    <span style="display: block; color: #6b7280; font-size: 14px;">Verified False:</span>
                    <span style="display: block; font-size: 20px; font-weight: 600; color: #ef4444;">${stats.verified_false || 0}</span>
                </div>
            </div>
        `;
        
        container.appendChild(speakerDiv);
    });
}

// Get verdict class
function getVerdictClass(verdict) {
    const v = (verdict || 'unverifiable').toLowerCase().replace(' ', '_');
    
    if (VERDICT_MAPPINGS[v]) {
        return VERDICT_MAPPINGS[v].class;
    }
    
    // Fallback for any unmapped verdicts
    return 'unverified';
}

// Get verdict icon
function getVerdictIcon(verdict) {
    const v = (verdict || 'unverifiable').toLowerCase().replace(' ', '_');
    
    if (VERDICT_MAPPINGS[v]) {
        return VERDICT_MAPPINGS[v].icon;
    }
    
    return 'fa-question-circle';
}

// Format verdict label
function formatVerdict(verdict) {
    const v = (verdict || 'unverifiable').toLowerCase().replace(' ', '_');
    
    if (VERDICT_MAPPINGS[v]) {
        return VERDICT_MAPPINGS[v].label;
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
        const response = await fetch(`/api/export/${currentJobId}/${format}`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `factcheck_${currentJobId}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            throw new Error('Export failed');
        }
    } catch (error) {
        showError('Error exporting results: ' + error.message);
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Reset analysis
function resetAnalysis() {
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    
    currentJobId = null;
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Reset form
function resetForm() {
    // Clear text input
    document.getElementById('text-input').value = '';
    document.getElementById('char-count').textContent = '0';
    
    // Clear file input
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-name').textContent = '';
    document.getElementById('file-drop-zone').style.display = 'block';
    
    // Reset to text input tab
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.input-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.querySelector('[data-tab="text"]').classList.add('active');
    document.getElementById('text-panel').classList.add('active');
}

// New analysis button
function newAnalysis() {
    resetAnalysis();
    resetForm();
}

// Utility function to escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
