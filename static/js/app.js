// Global variables
let currentMethod = 'text';
let currentJobId = null;
let pollingInterval = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tab switching
    initTabs();
    
    // Initialize file upload
    initFileUpload();
    
    // Initialize character counter
    initCharacterCounter();
    
    // Initialize dropdowns
    initDropdowns();
});

// Initialize tabs
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tab = this.dataset.tab;
            switchTab(tab);
        });
    });
}

// Switch between input tabs
function switchTab(tab) {
    currentMethod = tab;
    
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    
    // Update panels
    document.querySelectorAll('.input-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`${tab}-panel`).classList.add('active');
}

// Initialize file upload
function initFileUpload() {
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('file-input');
    
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
            handleFile(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

// Handle file selection
function handleFile(file) {
    // Validate file
    const validTypes = ['.txt', '.srt', '.vtt'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!validTypes.includes(fileExtension)) {
        showError('Please upload a valid file type (TXT, SRT, or VTT)');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB
        showError('File size must be less than 10MB');
        return;
    }
    
    // Update UI
    document.getElementById('file-drop-zone').style.display = 'none';
    document.getElementById('file-info').style.display = 'flex';
    document.getElementById('file-name').textContent = file.name;
    
    // Store file reference
    document.getElementById('file-input').files = [file];
}

// Remove file
function removeFile() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-drop-zone').style.display = 'flex';
    document.getElementById('file-info').style.display = 'none';
}

// Initialize character counter
function initCharacterCounter() {
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    textInput.addEventListener('input', () => {
        charCount.textContent = textInput.value.length.toLocaleString();
    });
}

// Initialize dropdowns
function initDropdowns() {
    // Dropdown functionality is handled by toggleDropdown function
}

// Toggle dropdown
function toggleDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const arrow = document.getElementById(dropdownId.replace('-dropdown', '-arrow'));
    
    if (dropdown.style.display === 'block') {
        dropdown.style.display = 'none';
        arrow.classList.remove('rotate');
    } else {
        // Close other dropdowns
        document.querySelectorAll('.dropdown-content').forEach(d => {
            d.style.display = 'none';
        });
        document.querySelectorAll('.dropdown-arrow').forEach(a => {
            a.classList.remove('rotate');
        });
        
        // Open this dropdown
        dropdown.style.display = 'block';
        arrow.classList.add('rotate');
    }
}

// Start analysis
async function startAnalysis() {
    // Clear any existing polling
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    
    let transcript = '';
    let source = '';
    
    try {
        // Get transcript based on method
        if (currentMethod === 'text') {
            transcript = document.getElementById('text-input').value.trim();
            source = 'Direct Input';
            
            if (!transcript) {
                showError('Please enter a transcript to analyze');
                return;
            }
        } else if (currentMethod === 'file') {
            const fileInput = document.getElementById('file-input');
            if (!fileInput.files || fileInput.files.length === 0) {
                showError('Please select a file to analyze');
                return;
            }
            
            const file = fileInput.files[0];
            transcript = await readFile(file);
            source = `File: ${file.name}`;
        }
        
        // Validate transcript
        if (!transcript || transcript.length < 50) {
            showError('Transcript is too short. Please provide more content to analyze.');
            return;
        }
        
        if (transcript.length > 50000) {
            showError('Transcript is too long. Maximum 50,000 characters allowed.');
            return;
        }
        
        // Disable analyze button
        const analyzeButton = document.getElementById('analyze-button');
        analyzeButton.disabled = true;
        
        // Send to API
        await analyzeTranscript(transcript, source);
        
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while processing your request');
        // Re-enable analyze button
        document.getElementById('analyze-button').disabled = false;
    }
}

// Read file
async function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

// Analyze transcript
async function analyzeTranscript(transcript, source) {
    // Show progress section, hide others
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
    
    // Reset progress
    updateProgress(0, 'Initializing analysis...');
    updateProgressSteps(1);
    
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
        
        // Store current job ID
        currentJobId = data.job_id;
        
        // Start polling for results
        pollJobStatus(data.job_id);
        
    } catch (error) {
        console.error('Analysis error:', error);
        showError(error.message || 'Failed to analyze transcript');
        resetAnalysis();
    }
}

// Poll job status
async function pollJobStatus(jobId) {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;
    
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${jobId}`);
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                throw new Error('Failed to get job status');
            }
            
            // Update progress
            const progress = data.progress || 0;
            updateProgress(progress, getProgressText(progress));
            updateProgressSteps(getProgressStep(progress));
            
            if (data.status === 'completed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                await loadResults(jobId);
            } else if (data.status === 'failed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                throw new Error(data.error || 'Analysis failed');
            }
            
            attempts++;
            if (attempts >= maxAttempts) {
                clearInterval(pollingInterval);
                pollingInterval = null;
                throw new Error('Analysis timed out');
            }
            
        } catch (error) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            console.error('Polling error:', error);
            showError(error.message || 'Failed to get analysis status');
            resetAnalysis();
        }
    }, 5000); // Poll every 5 seconds
}

// Update progress
function updateProgress(percent, text) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressFill.style.width = percent + '%';
    progressText.textContent = text;
}

// Get progress text
function getProgressText(progress) {
    if (progress < 20) return 'Processing transcript...';
    if (progress < 40) return 'Extracting claims...';
    if (progress < 60) return 'Fact-checking claims...';
    if (progress < 80) return 'Analyzing credibility...';
    if (progress < 100) return 'Finalizing results...';
    return 'Analysis complete!';
}

// Get progress step
function getProgressStep(progress) {
    if (progress < 25) return 1;
    if (progress < 50) return 2;
    if (progress < 75) return 3;
    return 4;
}

// Update progress steps
function updateProgressSteps(activeStep) {
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step-${i}`);
        if (step) {
            if (i <= activeStep) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        }
    }
}

// Load results
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
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('results-section').style.display = 'block';
        
        // Set up export buttons
        setupExportButtons(jobId);
        
    } catch (error) {
        console.error('Results error:', error);
        showError('Failed to load analysis results');
        resetAnalysis();
    }
}

// Display results
function displayResults(results) {
    // Update credibility score
    const score = results.credibility_score || 0;
    const credibilityValue = document.getElementById('credibility-value');
    const credibilityLabel = document.getElementById('credibility-label');
    const meterPointer = document.getElementById('credibility-pointer');
    
    credibilityValue.textContent = Math.round(score);
    credibilityLabel.textContent = getCredibilityLabel(score);
    
    // Position meter pointer
    if (meterPointer) {
        meterPointer.style.left = `${score}%`;
    }
    
    // Update stats
    updateStats(results);
    
    // Display summary
    const summaryContainer = document.getElementById('analysis-summary');
    summaryContainer.innerHTML = '';
    
    // Add speaker context if available
    if (results.speaker_context && results.speaker_context.speaker) {
        const contextHtml = window.generateSpeakerContextHTML ? 
            window.generateSpeakerContextHTML(results.speaker_context) : 
            generateBasicSpeakerContext(results.speaker_context);
        summaryContainer.innerHTML += contextHtml;
    }
    
    // Add conversational summary
    if (results.conversational_summary) {
        summaryContainer.innerHTML += `
            <div class="conversational-summary">
                <h4>Summary:</h4>
                <p>${results.conversational_summary}</p>
            </div>
        `;
    }
    
    // Display fact checks
    if (window.displayEnhancedFactChecks) {
        window.updateEnhancedStats(results);
        window.displayEnhancedFactChecks(results.fact_checks || []);
    } else {
        displayFactChecks(results.fact_checks || []);
    }
}

// Generate basic speaker context (fallback)
function generateBasicSpeakerContext(context) {
    let html = '<div class="speaker-context-section">';
    html += `<h4>About ${context.speaker}:</h4>`;
    
    if (context.criminal_record) {
        html += `<div class="alert alert-danger">
            <strong>⚖️ Criminal Record:</strong> ${context.criminal_record}
        </div>`;
    }
    
    if (context.fraud_history) {
        html += `<div class="alert alert-warning">
            <strong>💰 Fraud History:</strong> ${context.fraud_history}
        </div>`;
    }
    
    html += '</div><hr>';
    return html;
}

// Get credibility label
function getCredibilityLabel(score) {
    if (score >= 80) return 'Highly Credible';
    if (score >= 60) return 'Generally Credible';
    if (score >= 40) return 'Mixed Credibility';
    if (score >= 20) return 'Low Credibility';
    return 'Very Low Credibility';
}

// Update stats
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
    
    const totalClaims = results.fact_checks ? results.fact_checks.length : 0;
    
    document.getElementById('total-claims').textContent = totalClaims;
    document.getElementById('verified-claims').textContent = verifiedCount;
    document.getElementById('false-claims').textContent = falseCount;
    document.getElementById('unverified-claims').textContent = unverifiedCount;
}

// Display fact checks
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    if (!factChecks || factChecks.length === 0) {
        container.innerHTML = '<p>No fact checks available.</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        const verdict = check.verdict || 'unverified';
        const verdictClass = getVerdictClass(verdict);
        
        item.className = `fact-check-item ${verdictClass}`;
        
        item.innerHTML = `
            <div class="fact-check-header" onclick="toggleFactCheck('fact-check-details-${index}')">
                <div class="fact-check-claim">
                    <i class="fas fa-chevron-right toggle-icon" id="fact-check-details-${index}-icon"></i>
                    ${check.claim}
                </div>
                <div class="fact-check-verdict ${verdictClass}">
                    <i class="fas ${getVerdictIcon(verdict)}"></i>
                    ${getVerdictLabel(verdict)}
                </div>
            </div>
            <div class="fact-check-details-wrapper" id="fact-check-details-${index}" style="display: none;">
                <div class="fact-check-details">
                    ${check.explanation ? `
                        <div class="explanation-section">
                            <h4>Explanation</h4>
                            <p>${check.explanation}</p>
                        </div>
                    ` : ''}
                    ${check.confidence ? `
                        <div class="confidence-section">
                            <h4>Confidence Level</h4>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${check.confidence}%"></div>
                            </div>
                            <span class="confidence-text">${check.confidence}% confident</span>
                        </div>
                    ` : ''}
                    ${check.source ? `
                        <div class="sources-section">
                            <h4>Source</h4>
                            <p>${check.source}</p>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Get verdict icon
function getVerdictIcon(verdict) {
    const verdictLower = verdict.toLowerCase();
    if (verdictLower === 'true' || verdictLower === 'mostly_true') return 'fa-check-circle';
    if (verdictLower === 'false' || verdictLower === 'mostly_false') return 'fa-times-circle';
    if (verdictLower === 'mixed') return 'fa-adjust';
    if (verdictLower === 'misleading' || verdictLower === 'deceptive') return 'fa-exclamation-triangle';
    if (verdictLower === 'lacks_context') return 'fa-info-circle';
    if (verdictLower === 'unsubstantiated') return 'fa-question-circle';
    return 'fa-question-circle';
}

// Get verdict label
function getVerdictLabel(verdict) {
    const verdictLower = verdict.toLowerCase();
    const labelMap = {
        'true': 'True',
        'mostly_true': 'Mostly True',
        'false': 'False',
        'mostly_false': 'Mostly False',
        'mixed': 'Mixed',
        'misleading': 'Deceptive',
        'deceptive': 'Deceptive',
        'lacks_context': 'Lacks Context',
        'unsubstantiated': 'Unsubstantiated',
        'unverified': 'Unverified'
    };
    return labelMap[verdictLower] || 'Unverified';
}

// Toggle fact check details
function toggleFactCheck(detailsId) {
    const details = document.getElementById(detailsId);
    const icon = document.getElementById(`${detailsId}-icon`);
    
    if (details.style.display === 'none') {
        details.style.display = 'block';
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');
    } else {
        details.style.display = 'none';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-right');
    }
}

// Get verdict class
function getVerdictClass(verdict) {
    const verdictLower = verdict.toLowerCase();
    if (verdictLower === 'true' || verdictLower === 'mostly_true') return 'true';
    if (verdictLower === 'false' || verdictLower === 'mostly_false') return 'false';
    if (verdictLower === 'mixed') return 'mixed';
    if (verdictLower === 'misleading' || verdictLower === 'deceptive') return 'deceptive';
    if (verdictLower === 'lacks_context') return 'lacks_context';
    if (verdictLower === 'unsubstantiated') return 'unsubstantiated';
    return 'unverified';
}

// Setup export buttons
function setupExportButtons(jobId) {
    // Export button functionality
    window.exportResults = function(format) {
        if (!currentJobId) {
            showError('No results to export');
            return;
        }
        window.location.href = `/api/export/${currentJobId}/${format}`;
    };
}

// Reset analysis
function resetAnalysis() {
    // Clear any active polling
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    
    // Reset current job
    currentJobId = null;
    
    // Show input section, hide others
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    
    // Clear form inputs
    document.getElementById('text-input').value = '';
    document.getElementById('char-count').textContent = '0';
    removeFile();
    
    // Re-enable analyze button
    document.getElementById('analyze-button').disabled = false;
    
    // Reset to text tab
    switchTab('text');
    
    // Scroll to top
    window.scrollTo(0, 0);
}

// Show error message
function showError(message) {
    // Create error alert
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-error';
    alertDiv.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
    `;
    
    // Add to page
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Remove after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
    
    // Also show in console
    console.error('Error:', message);
}

// Make functions available globally
window.startAnalysis = startAnalysis;
window.displayResults = displayResults;
window.resetAnalysis = resetAnalysis;
window.removeFile = removeFile;
window.toggleDropdown = toggleDropdown;
window.exportResults = exportResults;
window.toggleFactCheck = toggleFactCheck;
