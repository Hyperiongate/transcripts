// Main application JavaScript
// Enhanced with proper verdict mapping and visual improvements

// Updated verdict mappings to handle all verdict types
const VERDICT_MAPPINGS = {
    // Standard verdicts
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
    
    // Enhanced verdict types
    'empty_rhetoric': {
        label: 'Empty Rhetoric',
        class: 'rhetoric',
        icon: 'fa-wind',
        color: '#94a3b8'
    },
    'unsubstantiated_prediction': {
        label: 'Unsubstantiated Prediction',
        class: 'prediction',
        icon: 'fa-crystal-ball',
        color: '#a78bfa'
    },
    'pattern_of_false_promises': {
        label: 'Pattern of False Promises',
        class: 'pattern',
        icon: 'fa-history',
        color: '#f97316'
    },
    
    // Internal verdict mappings
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
    'nearly_true': {
        label: 'Nearly True',
        class: 'true',
        icon: 'fa-check-circle',
        color: '#6ee7b7'
    },
    'exaggeration': {
        label: 'Exaggeration',
        class: 'mixed',
        icon: 'fa-expand-arrows-alt',
        color: '#fbbf24'
    },
    'misleading': {
        label: 'Misleading',
        class: 'false',
        icon: 'fa-exclamation-triangle',
        color: '#f59e0b'
    },
    'mostly_false': {
        label: 'Mostly False',
        class: 'false',
        icon: 'fa-times-circle',
        color: '#f87171'
    },
    'needs_context': {
        label: 'Needs Context',
        class: 'unverified',
        icon: 'fa-question-circle',
        color: '#8b5cf6'
    },
    'opinion': {
        label: 'Opinion',
        class: 'opinion',
        icon: 'fa-comment',
        color: '#6366f1'
    },
    'mixed': {
        label: 'Mixed',
        class: 'mixed',
        icon: 'fa-adjust',
        color: '#f59e0b'
    }
};

// Global variables
let currentJobId = null;
let pollInterval = null;
let currentFile = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// Initialize application
function initializeApp() {
    initializeTabs();
    initializeCharacterCounter();
    initializeFileUpload();
    initializeAnalyzeButton();
}

// Initialize tabs functionality
function initializeTabs() {
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
}

// Initialize character counter
function initializeCharacterCounter() {
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    if (textInput && charCount) {
        textInput.addEventListener('input', () => {
            const length = textInput.value.length;
            charCount.textContent = length.toLocaleString();
            
            // Warn if approaching limit
            if (length > 45000) {
                charCount.style.color = '#ef4444';
            } else {
                charCount.style.color = '#6b7280';
            }
        });
    }
}

// Initialize file upload functionality
function initializeFileUpload() {
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('file-drop-zone');
    
    if (!fileInput || !dropZone) return;
    
    // Click to browse
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    // File selected
    fileInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop
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
            handleFile(files[0]);
        }
    });
}

// Initialize analyze button
function initializeAnalyzeButton() {
    const analyzeButton = document.getElementById('analyze-button');
    if (analyzeButton) {
        analyzeButton.addEventListener('click', startAnalysis);
    }
}

// Handle file selection
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

// Handle file processing
function handleFile(file) {
    // Validate file
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['.txt', '.srt', '.vtt'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (file.size > maxSize) {
        showError('File too large. Maximum size is 10MB.');
        return;
    }
    
    if (!allowedTypes.includes(fileExtension)) {
        showError('Invalid file type. Please upload TXT, SRT, or VTT files.');
        return;
    }
    
    currentFile = file;
    showFileInfo(file);
}

// Show file information
function showFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const dropZone = document.getElementById('file-drop-zone');
    
    if (fileInfo && fileName && dropZone) {
        fileName.textContent = file.name;
        fileInfo.style.display = 'flex';
        dropZone.style.display = 'none';
    }
}

// Remove selected file
function removeFile() {
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const dropZone = document.getElementById('file-drop-zone');
    
    if (fileInput) fileInput.value = '';
    if (fileInfo) fileInfo.style.display = 'none';
    if (dropZone) dropZone.style.display = 'block';
    
    currentFile = null;
}

// Start analysis - main function called by button
async function startAnalysis() {
    const activePanel = document.querySelector('.input-panel.active');
    const tabType = activePanel.id.replace('-panel', '');
    
    let transcript = '';
    
    try {
        if (tabType === 'text') {
            transcript = document.getElementById('text-input').value;
            if (!transcript.trim()) {
                showError('Please enter a transcript to analyze');
                return;
            }
        } else if (tabType === 'file') {
            if (!currentFile) {
                showError('Please select a file to analyze');
                return;
            }
            transcript = await readFileContent(currentFile);
        }
        
        if (transcript.length > 50000) {
            showError('Transcript too long. Maximum 50,000 characters allowed.');
            return;
        }
        
        // Show loading state
        showProgress();
        
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ transcript: transcript })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Start polling for results
        pollForResults();
        
    } catch (error) {
        hideProgress();
        showError('Error starting analysis: ' + error.message);
    }
}

// Read file content
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

// Poll for job results
function pollForResults() {
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            
            if (!response.ok) {
                throw new Error(`Status check failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update progress
            updateProgress(data.progress || 0, data.message || 'Processing...');
            
            if (data.status === 'completed') {
                clearInterval(pollInterval);
                const resultsResponse = await fetch(`/api/results/${currentJobId}`);
                
                if (!resultsResponse.ok) {
                    throw new Error('Failed to get results');
                }
                
                const results = await resultsResponse.json();
                displayResults(results);
                hideProgress();
            } else if (data.status === 'failed') {
                clearInterval(pollInterval);
                hideProgress();
                showError('Analysis failed: ' + (data.error || 'Unknown error'));
            }
            
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideProgress();
                showError('Analysis timed out. Please try again.');
            }
            
        } catch (error) {
            clearInterval(pollInterval);
            hideProgress();
            showError('Error checking status: ' + error.message);
        }
    }, 1000); // Poll every second
}

// Display results with enhanced visuals
function displayResults(results) {
    hideProgress();
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    // Display enhanced summary with markdown support
    displaySummary(results.summary || 'No summary available');
    
    // Display credibility score
    displayCredibilityScore(results.credibility_score);
    
    // Update statistics with proper mapping
    updateStatistics(results.credibility_score?.breakdown || {});
    
    // Display fact checks with enhanced visuals
    displayFactChecks(results.fact_checks || []);
    
    // Display speaker analysis if available
    if (results.speakers && results.speakers.length > 0) {
        displaySpeakerInfo(results.speakers);
    }
}

// Display summary with markdown formatting
function displaySummary(summary) {
    const summaryElement = document.getElementById('summary-text');
    if (!summaryElement) return;
    
    // Convert markdown to HTML
    let summaryHtml = summary
        .replace(/^### (.*$)/gim, '<h3 style="color: #1f2937; margin: 16px 0 8px 0; font-size: 18px;">$1</h3>')
        .replace(/^## (.*$)/gim, '<h2 style="color: #1f2937; margin: 20px 0 12px 0; font-size: 20px;">$1</h2>')
        .replace(/^# (.*$)/gim, '<h1 style="color: #1f2937; margin: 24px 0 16px 0; font-size: 24px;">$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/🟢/g, '<span style="color: #10b981;">🟢</span>')
        .replace(/🟡/g, '<span style="color: #f59e0b;">🟡</span>')
        .replace(/🟠/g, '<span style="color: #f97316;">🟠</span>')
        .replace(/🔴/g, '<span style="color: #ef4444;">🔴</span>')
        .replace(/⚪/g, '<span style="color: #9ca3af;">⚪</span>');
    
    summaryElement.innerHTML = `<p>${summaryHtml}</p>`;
}

// Display credibility score with visual meter
function displayCredibilityScore(credScore) {
    if (!credScore) return;
    
    const score = credScore.score || 0;
    const label = credScore.label || 'Unknown';
    
    // Update score display
    const scoreElement = document.getElementById('credibility-value');
    const labelElement = document.getElementById('credibility-label');
    const pointerElement = document.getElementById('credibility-pointer');
    
    if (scoreElement) {
        scoreElement.textContent = score;
        scoreElement.style.color = getScoreColor(score);
    }
    
    if (labelElement) {
        labelElement.textContent = label;
    }
    
    // Update meter pointer
    if (pointerElement) {
        const percentage = Math.max(0, Math.min(100, score));
        pointerElement.style.left = `calc(${percentage}% - 3px)`;
    }
}

// Update statistics display
function updateStatistics(breakdown) {
    const elements = {
        'verified-true-count': breakdown.verified_true || 0,
        'verified-false-count': breakdown.verified_false || 0,
        'partially-accurate-count': breakdown.partially_accurate || 0,
        'unverifiable-count': breakdown.unverifiable || 0
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

// Display fact checks with enhanced formatting
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-checks-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280; font-style: italic;">No claims found to fact-check.</p>';
        return;
    }
    
    // Filter out null results
    const validFactChecks = factChecks.filter(fc => fc !== null);
    
    validFactChecks.forEach((check, index) => {
        const item = document.createElement('div');
        const verdictInfo = VERDICT_MAPPINGS[check.verdict] || VERDICT_MAPPINGS['unverifiable'];
        
        item.className = `fact-check-item verdict-${verdictInfo.class}`;
        
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-number">#${index + 1}</div>
                <div class="fact-check-verdict" style="background-color: ${verdictInfo.color}20; color: ${verdictInfo.color}; border: 1px solid ${verdictInfo.color};">
                    <i class="fas ${verdictInfo.icon}"></i>
                    ${verdictInfo.label}
                </div>
                ${check.speaker && check.speaker !== 'Unknown' ? 
                    `<div class="fact-check-speaker">
                        <i class="fas fa-user"></i> ${escapeHtml(check.speaker)}
                    </div>` : ''}
            </div>
            <div class="fact-check-content">
                <p class="fact-check-claim">"${escapeHtml(check.claim || check.text || '')}"</p>
                <div class="fact-check-explanation">
                    ${formatExplanation(check.explanation || 'No explanation available.')}
                </div>
                ${check.confidence ? 
                    `<div class="fact-check-confidence">
                        <strong>Confidence:</strong> ${check.confidence}%
                    </div>` : ''}
                ${check.sources && check.sources.length > 0 ?
                    `<div class="fact-check-source">
                        <i class="fas fa-link"></i> <strong>Sources:</strong> ${check.sources.join(', ')}
                    </div>` : ''}
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Display speaker information
function displaySpeakerInfo(speakers) {
    const container = document.getElementById('speaker-analysis-container');
    if (!container || !speakers.length) return;
    
    container.innerHTML = `
        <div style="background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
            <h4 style="margin: 0 0 12px 0; color: #374151;">
                <i class="fas fa-users" style="color: #3b82f6; margin-right: 8px;"></i>
                Speakers Analyzed
            </h4>
            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                ${speakers.map(speaker => `
                    <span style="background: white; padding: 6px 12px; border-radius: 6px; font-weight: 500; color: #374151; border: 1px solid #e5e7eb;">
                        ${escapeHtml(speaker)}
                    </span>
                `).join('')}
            </div>
        </div>
    `;
}

// Format explanation with better structure
function formatExplanation(explanation) {
    if (!explanation) return 'No explanation available.';
    
    return explanation
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/PATTERN DETECTED:/g, '<span style="color: #ef4444; font-weight: bold;">⚠️ PATTERN DETECTED:</span>')
        .replace(/CONCLUSION:/g, '<strong>CONCLUSION:</strong>')
        .replace(/CONTEXT AND BALANCE:/g, '<strong>CONTEXT AND BALANCE:</strong>')
        .replace(/SPEAKER TRACK RECORD:/g, '<strong>SPEAKER TRACK RECORD:</strong>');
}

// Helper functions
function getScoreColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#fbbf24';
    if (score >= 40) return '#f59e0b';
    if (score >= 20) return '#f87171';
    return '#ef4444';
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// UI state management
function showProgress() {
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
}

function hideProgress() {
    document.getElementById('progress-section').style.display = 'none';
}

function updateProgress(progress, message) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    if (progressFill) {
        progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }
    if (progressText) {
        progressText.textContent = message;
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-circle" style="margin-right: 8px;"></i>
        <span>${escapeHtml(message)}</span>
        <button onclick="this.parentElement.remove()" style="background: none; border: none; color: white; margin-left: 12px; cursor: pointer; font-size: 18px; padding: 0;">×</button>
    `;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

// Export functionality
async function exportResults(format) {
    if (!currentJobId) {
        showError('No results to export');
        return;
    }
    
    try {
        const response = await fetch(`/api/export/${currentJobId}/${format}`);
        
        if (response.ok) {
            if (format === 'json') {
                const data = await response.json();
                downloadJSON(data, `factcheck_${currentJobId}.json`);
            } else {
                const blob = await response.blob();
                downloadBlob(blob, `factcheck_${currentJobId}.${format}`);
            }
        } else {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Export failed');
        }
    } catch (error) {
        showError('Error exporting results: ' + error.message);
    }
}

// Download JSON data
function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadBlob(blob, filename);
}

// Download blob as file
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// Start new analysis
function newAnalysis() {
    currentJobId = null;
    currentFile = null;
    
    // Reset UI
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Clear inputs
    const textInput = document.getElementById('text-input');
    if (textInput) {
        textInput.value = '';
        document.getElementById('char-count').textContent = '0';
    }
    
    // Clear file
    removeFile();
    
    // Clear any polling
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    
    // Scroll to top
    window.scrollTo(0, 0);
}

// Global functions for HTML onclick handlers
window.startAnalysis = startAnalysis;
window.removeFile = removeFile;
window.newAnalysis = newAnalysis;
window.exportResults = exportResults;
