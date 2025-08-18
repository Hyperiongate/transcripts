// Transcript Fact Checker - Main JavaScript

// Global variables
let currentJobId = null;
let pollInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeFileUpload();
    initializeTextInput();
});

// Tab functionality
function initializeTabs() {
    const tabs = document.querySelectorAll('.tab-button');
    const panels = document.querySelectorAll('.input-panel');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding panel
            tab.classList.add('active');
            const tabName = tab.getAttribute('data-tab');
            document.getElementById(`${tabName}-panel`).classList.add('active');
        });
    });
}

// File upload functionality
function initializeFileUpload() {
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('file-input');
    
    if (!dropZone || !fileInput) {
        console.warn('File upload elements not found');
        return;
    }
    
    // Click to upload
    dropZone.addEventListener('click', () => fileInput.click());
    
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
            handleFileSelect(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

// Text input character counter
function initializeTextInput() {
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    if (!textInput || !charCount) {
        console.warn('Text input elements not found');
        return;
    }
    
    textInput.addEventListener('input', () => {
        charCount.textContent = textInput.value.length;
    });
}

// Handle file selection
function handleFileSelect(file) {
    const allowedTypes = ['.txt', '.srt', '.vtt'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(fileExt)) {
        alert('Please upload a TXT, SRT, or VTT file.');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB.');
        return;
    }
    
    // Show file info
    document.getElementById('file-info').style.display = 'flex';
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-drop-zone').style.display = 'none';
    
    // Store file reference
    const fileInput = document.getElementById('file-input');
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
}

// Remove selected file
function removeFile() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-drop-zone').style.display = 'block';
}

// Start analysis - MAIN FUNCTION
async function startAnalysis() {
    // Disable button to prevent double submission
    const analyzeButton = document.getElementById('analyze-button');
    analyzeButton.disabled = true;
    
    try {
        // Get active tab
        const activeTab = document.querySelector('.tab-button.active').getAttribute('data-tab');
        
        let analysisData = {
            type: activeTab
        };
        
        // Validate and prepare data based on input type
        if (activeTab === 'text') {
            const text = document.getElementById('text-input').value.trim();
            if (!text) {
                alert('Please enter some text to analyze.');
                analyzeButton.disabled = false;
                return;
            }
            if (text.length < 50) {
                alert('Please enter at least 50 characters of text.');
                analyzeButton.disabled = false;
                return;
            }
            if (text.length > 50000) {
                alert('Text is too long. Maximum 50,000 characters allowed.');
                analyzeButton.disabled = false;
                return;
            }
            analysisData.transcript = text;
            
        } else if (activeTab === 'file') {
            const fileInput = document.getElementById('file-input');
            if (!fileInput.files.length) {
                alert('Please select a file to analyze.');
                analyzeButton.disabled = false;
                return;
            }
            
            // For file upload, we need to read the file content first
            const file = fileInput.files[0];
            const reader = new FileReader();
            
            reader.onload = async function(e) {
                const fileContent = e.target.result;
                
                try {
                    showProgress();
                    updateProgressMessage('Processing file...');
                    
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            transcript: fileContent,
                            source: `File: ${file.name}`,
                            type: 'file'
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        currentJobId = result.job_id;
                        console.log('Analysis started with job ID:', currentJobId);
                        pollJobStatus();
                    } else {
                        hideProgress();
                        alert(result.error || 'Analysis failed.');
                    }
                } catch (error) {
                    hideProgress();
                    alert('Error: ' + error.message);
                } finally {
                    analyzeButton.disabled = false;
                }
            };
            
            reader.onerror = function() {
                alert('Error reading file');
                analyzeButton.disabled = false;
            };
            
            reader.readAsText(file);
            return;
        }
        
        // For text input
        try {
            showProgress();
            updateProgressMessage('Processing text...');
            
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(analysisData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                currentJobId = result.job_id;
                console.log('Analysis started with job ID:', currentJobId);
                console.log('Source:', result.source);
                pollJobStatus();
            } else {
                hideProgress();
                alert(result.error || 'Analysis failed.');
            }
        } catch (error) {
            hideProgress();
            alert('Error: ' + error.message);
        }
        
    } catch (error) {
        console.error('Analysis error:', error);
        alert('An error occurred. Please try again.');
    } finally {
        analyzeButton.disabled = false;
    }
}

// Show progress section
function showProgress() {
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
}

// Hide progress section
function hideProgress() {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
}

// Update progress message
function updateProgressMessage(message) {
    document.getElementById('progress-text').textContent = message;
}

// Update progress bar
function updateProgress(percent) {
    document.getElementById('progress-fill').style.width = percent + '%';
    
    // Update step indicators
    const steps = ['step-1', 'step-2', 'step-3', 'step-4'];
    const stepPercent = 100 / steps.length;
    
    steps.forEach((stepId, index) => {
        const step = document.getElementById(stepId);
        if (percent >= (index + 1) * stepPercent) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

// Poll job status
async function pollJobStatus() {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const result = await response.json();
            
            if (result.success) {
                // Update progress
                updateProgress(result.progress || 0);
                
                // Update message based on status
                switch (result.status) {
                    case 'processing':
                        updateProgressMessage('Processing transcript...');
                        break;
                    case 'extracting':
                        updateProgressMessage('Extracting claims...');
                        break;
                    case 'checking':
                        updateProgressMessage('Fact-checking claims...');
                        break;
                    case 'analyzing':
                        updateProgressMessage('Analyzing credibility...');
                        break;
                    case 'completed':
                        updateProgressMessage('Analysis complete!');
                        clearInterval(pollInterval);
                        await loadResults();
                        break;
                    case 'failed':
                        clearInterval(pollInterval);
                        hideProgress();
                        alert('Analysis failed: ' + (result.error || 'Unknown error'));
                        break;
                }
            } else {
                attempts++;
                if (attempts >= maxAttempts) {
                    clearInterval(pollInterval);
                    hideProgress();
                    alert('Analysis timed out. Please try again.');
                }
            }
        } catch (error) {
            console.error('Poll error:', error);
            clearInterval(pollInterval);
            hideProgress();
            alert('Error checking status. Please refresh the page.');
        }
    }, 2000); // Poll every 2 seconds
}

// Load and display results
async function loadResults() {
    try {
        const response = await fetch(`/api/results/${currentJobId}`);
        const result = await response.json();
        
        if (result.success && result.data) {
            displayResults(result.data);
        } else {
            throw new Error('Failed to load results');
        }
    } catch (error) {
        console.error('Load results error:', error);
        alert('Error loading results. Please refresh the page.');
    }
}

// Display results
function displayResults(data) {
    // Hide progress, show results
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    // Update credibility score
    const score = data.credibility_score || 0;
    document.getElementById('credibility-value').textContent = Math.round(score);
    
    // Use enhanced getCredibilityLabel if available, otherwise use local version
    const labelFunc = window.getCredibilityLabel || getCredibilityLabel;
    document.getElementById('credibility-label').textContent = labelFunc(score);
    
    // Update credibility meter pointer
    const pointer = document.getElementById('credibility-pointer');
    const position = (score / 100) * 100; // Percentage position
    pointer.style.left = `calc(${position}% - 3px)`; // Center the pointer
    
    // Update summary
    document.getElementById('analysis-summary').textContent = data.conversational_summary || data.summary || 'Analysis complete.';
    
    // Update statistics
    const stats = data.statistics || {};
    document.getElementById('total-claims').textContent = data.total_claims || stats.total_claims || 0;
    document.getElementById('verified-claims').textContent = stats.verified || 0;
    document.getElementById('false-claims').textContent = stats.false || 0;
    document.getElementById('unverified-claims').textContent = stats.unverified || 0;
    
    // Use enhanced display function if available, otherwise use basic display
    if (typeof window.displayResults === 'function' && window.displayResults !== displayResults) {
        // Call enhanced displayResults from enhanced.js
        window.displayResults(data);
    } else {
        // Display fact checks with basic functionality
        displayFactChecks(data.fact_checks || []);
    }
}

// Get credibility label based on score
function getCredibilityLabel(score) {
    if (score >= 80) return 'Highly Credible';
    if (score >= 60) return 'Moderately Credible';
    if (score >= 40) return 'Low Credibility';
    return 'Very Low Credibility';
}

// Make it available globally if not already defined by enhanced.js
if (typeof window.getCredibilityLabel === 'undefined') {
    window.getCredibilityLabel = getCredibilityLabel;
}

// Basic fact check display (will be overridden by enhanced version)
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p>No claims found to fact-check.</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        item.className = 'fact-check-item';
        
        const verdict = check.verdict || 'unverified';
        const verdictClass = verdict.toLowerCase();
        
        item.innerHTML = `
            <div class="fact-check-header">
                <span class="fact-check-number">#${index + 1}</span>
                <span class="fact-check-verdict ${verdictClass}">
                    <i class="fas fa-${verdictClass === 'true' ? 'check' : verdictClass === 'false' ? 'times' : 'question'}-circle"></i>
                    ${verdict}
                </span>
            </div>
            <div class="fact-check-claim">
                <strong>Claim:</strong> ${check.claim}
            </div>
            <div class="fact-check-details">
                <p><strong>Explanation:</strong> ${check.explanation || 'No explanation available.'}</p>
                ${check.confidence ? `<p><strong>Confidence:</strong> ${check.confidence}%</p>` : ''}
            </div>
            ${check.source ? `
                <div class="fact-check-source">
                    <strong>Source:</strong> 
                    ${check.source_url ? `<a href="${check.source_url}" target="_blank">${check.source}</a>` : check.source}
                </div>
            ` : ''}
        `;
        
        container.appendChild(item);
    });
}

// Export results
async function exportResults(format) {
    if (!currentJobId) {
        alert('No results to export');
        return;
    }
    
    try {
        const response = await fetch(`/api/export/${currentJobId}/${format}`, {
            method: 'GET'
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `fact-check-report-${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const result = await response.json();
            alert('Export failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        alert('Export error: ' + error.message);
    }
}

// Reset for new analysis
function resetAnalysis() {
    currentJobId = null;
    
    // Clear inputs
    document.getElementById('text-input').value = '';
    document.getElementById('char-count').textContent = '0';
    removeFile();
    
    // Reset UI
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset progress
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Initializing...';
    
    // Reset step indicators
    const steps = ['step-1', 'step-2', 'step-3', 'step-4'];
    steps.forEach(stepId => {
        document.getElementById(stepId).classList.remove('active');
    });
    
    // Clear any intervals
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}
