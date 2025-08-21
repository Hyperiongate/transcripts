// Global variables
let currentJobId = null;
let statusCheckInterval = null;
let progressTimeout = null;

// Tab switching
function switchTab(tabName) {
    // Remove active class from all tabs and panels
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.input-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // Add active class to selected tab and panel
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-panel`).classList.add('active');
}

// Initialize tab buttons
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => switchTab(button.dataset.tab));
    });
    
    // Character counter for text input
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    textInput.addEventListener('input', () => {
        charCount.textContent = textInput.value.length;
    });
    
    // File input handler
    const fileInput = document.getElementById('file-input');
    fileInput.addEventListener('change', handleFileSelect);
    
    // File drop zone
    const dropZone = document.getElementById('file-drop-zone');
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
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect({ target: { files: e.dataTransfer.files } });
        }
    });
});

// File handling
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    
    fileName.textContent = file.name;
    fileInfo.style.display = 'flex';
    
    // Read file content
    const reader = new FileReader();
    reader.onload = function(e) {
        // Store content for later use
        fileInput.dataset.content = e.target.result;
    };
    reader.readAsText(file);
}

function removeFile() {
    const fileInput = document.getElementById('file-input');
    fileInput.value = '';
    fileInput.dataset.content = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-name').textContent = '';
}

// Analysis functions
async function startAnalysis() {
    const activePanel = document.querySelector('.input-panel.active');
    const activeTab = activePanel.id.replace('-panel', '');
    
    let transcript = '';
    let source = '';
    
    if (activeTab === 'text') {
        transcript = document.getElementById('text-input').value;
        source = 'Direct Input';
    } else if (activeTab === 'file') {
        const fileInput = document.getElementById('file-input');
        transcript = fileInput.dataset.content || '';
        source = 'File Upload';
    }
    
    if (!transcript.trim()) {
        showError('Please provide a transcript to analyze');
        return;
    }
    
    // Show progress section
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    
    // Reset progress
    updateProgress(0, 'Starting analysis...');
    
    try {
        const response = await analyzeTranscript(transcript, source);
        if (response.success) {
            currentJobId = response.job_id;
            // Start polling for status with higher frequency
            startStatusPolling();
        } else {
            throw new Error(response.error || 'Failed to start analysis');
        }
    } catch (error) {
        showError(error.message);
        resetToInput();
    }
}

async function analyzeTranscript(transcript, source) {
    const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ transcript, source })
    });
    
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Analysis failed');
    }
    
    return data;
}

function startStatusPolling() {
    // Clear any existing intervals
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    if (progressTimeout) {
        clearTimeout(progressTimeout);
    }
    
    // Check status every 500ms for real-time updates
    statusCheckInterval = setInterval(checkJobStatus, 500);
    
    // Set a timeout for 5 minutes
    progressTimeout = setTimeout(() => {
        clearInterval(statusCheckInterval);
        showError('Analysis timed out. Please try with a shorter transcript.');
        resetToInput();
    }, 300000); // 5 minutes
}

async function checkJobStatus() {
    if (!currentJobId) return;
    
    try {
        const response = await fetch(`/api/status/${currentJobId}`);
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Failed to check status');
        }
        
        // Update progress bar and message
        updateProgress(data.progress, data.message);
        
        // Update step indicators
        updateStepIndicators(data.progress);
        
        if (data.status === 'completed') {
            clearInterval(statusCheckInterval);
            clearTimeout(progressTimeout);
            await loadResults();
        } else if (data.status === 'failed') {
            clearInterval(statusCheckInterval);
            clearTimeout(progressTimeout);
            showError(data.error || 'Analysis failed');
            resetToInput();
        }
    } catch (error) {
        console.error('Status check error:', error);
        // Don't stop polling on error, just log it
    }
}

function updateProgress(progress, message) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressFill.style.width = `${progress}%`;
    progressText.textContent = message || 'Processing...';
}

function updateStepIndicators(progress) {
    const steps = {
        'step-1': 25,  // Processing
        'step-2': 40,  // Extracting Claims
        'step-3': 70,  // Fact Checking
        'step-4': 90   // Generating Report
    };
    
    Object.entries(steps).forEach(([stepId, threshold]) => {
        const stepElement = document.getElementById(stepId);
        if (progress >= threshold) {
            stepElement.classList.add('active');
        } else {
            stepElement.classList.remove('active');
        }
    });
}

async function loadResults() {
    try {
        const response = await fetch(`/api/results/${currentJobId}`);
        const results = await response.json();
        
        if (!response.ok || !results.success) {
            throw new Error(results.error || 'Failed to load results');
        }
        
        // Hide progress, show results
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('results-section').style.display = 'block';
        
        // Display results
        displayResults(results);
    } catch (error) {
        showError(error.message);
        resetToInput();
    }
}

function displayResults(results) {
    // Update credibility meter - using the correct element IDs from your HTML
    const credibilityValue = document.getElementById('credibility-value');
    const credibilityLabel = document.getElementById('credibility-label');
    const credibilityPointer = document.getElementById('credibility-pointer');
    
    // Set the score value
    credibilityValue.textContent = results.credibility_score || 0;
    credibilityLabel.textContent = results.credibility_label || 'Unknown';
    
    // Position the pointer on the meter (0-100% mapped to the meter width)
    const score = results.credibility_score || 0;
    credibilityPointer.style.left = `${score}%`;
    
    // Update stats
    updateStats(results);
    
    // Display summary
    const summaryContainer = document.getElementById('analysis-summary');
    summaryContainer.innerHTML = `We analyzed ${results.total_claims || 0} claims from your transcript. 
        ${results.true_claims || 0} were verified as true, 
        ${results.false_claims || 0} were found to be false, 
        ${results.mixed_claims || 0} were mixed, and 
        ${results.unverified_claims || 0} could not be verified.`;
    
    // Display fact checks
    displayFactChecks(results.fact_checks || []);
}

function updateStats(results) {
    const stats = {
        'total-claims': results.total_claims || 0,
        'verified-claims': results.true_claims || 0,
        'false-claims': results.false_claims || 0,
        'unverified-claims': results.unverified_claims || 0
    };
    
    for (const [id, value] of Object.entries(stats)) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }
}

function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280;">No fact checks to display</p>';
        return;
    }
    
    factChecks.forEach((check, index) => {
        const item = document.createElement('div');
        const verdict = check.verdict || 'unverified';
        const verdictClass = getVerdictClass(verdict);
        
        item.className = `fact-check-item ${verdictClass}`;
        
        // Use enhanced template if available
        if (window.createFactCheckItem) {
            item.innerHTML = window.createFactCheckItem(check, index);
        } else {
            // Basic template
            item.innerHTML = `
                <div style="padding: 20px;">
                    <div class="fact-check-header">
                        <div class="fact-check-claim">${check.claim}</div>
                        <div class="fact-check-verdict ${verdictClass}">
                            <i class="fas ${getVerdictIcon(verdict)}"></i>
                            ${verdict.toUpperCase().replace('_', ' ')}
                        </div>
                    </div>
                    ${check.explanation ? `
                        <div class="fact-check-details">
                            <p>${check.explanation}</p>
                            ${check.sources && check.sources.length > 0 ? 
                                `<div class="sources">Sources: ${check.sources.join(', ')}</div>` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }
        
        container.appendChild(item);
    });
}

function getVerdictClass(verdict) {
    const mapping = {
        'true': 'true',
        'mostly_true': 'true',
        'mostly true': 'true',
        'mixed': 'unverified',
        'unclear': 'unverified',
        'misleading': 'false',
        'lacks_context': 'unverified',
        'lacks context': 'unverified',
        'mostly_false': 'false',
        'mostly false': 'false',
        'false': 'false',
        'unverified': 'unverified',
        'error': 'unverified'
    };
    
    return mapping[verdict.toLowerCase()] || 'unverified';
}

function getVerdictIcon(verdict) {
    const icons = {
        'true': 'fa-check-circle',
        'mostly_true': 'fa-check-circle',
        'mostly true': 'fa-check-circle',
        'mixed': 'fa-question-circle',
        'unclear': 'fa-question-circle',
        'misleading': 'fa-exclamation-triangle',
        'lacks_context': 'fa-info-circle',
        'lacks context': 'fa-info-circle',
        'mostly_false': 'fa-times-circle',
        'mostly false': 'fa-times-circle',
        'false': 'fa-times-circle',
        'unverified': 'fa-question-circle',
        'error': 'fa-exclamation-circle'
    };
    
    return icons[verdict.toLowerCase()] || 'fa-question-circle';
}

// Error handling
function showError(message) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-error';
    alert.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #fee2e2;
        border: 1px solid #fecaca;
        color: #dc2626;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    alert.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
    `;
    
    // Add to page
    document.body.appendChild(alert);
    
    // Remove after 5 seconds
    setTimeout(() => {
        alert.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

function resetToInput() {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Clear intervals
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    if (progressTimeout) {
        clearTimeout(progressTimeout);
        progressTimeout = null;
    }
}

// Export functions
async function exportResults(format) {
    if (!currentJobId) return;
    
    if (format === 'pdf') {
        showLoader('Generating PDF...');
        try {
            const response = await fetch(`/api/export/${currentJobId}/pdf`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `fact-check-report-${currentJobId}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                showSuccess('PDF downloaded successfully');
            } else {
                const error = await response.json();
                showError(error.error || 'Failed to generate PDF');
            }
        } catch (error) {
            console.error('Export error:', error);
            showError('Failed to export results');
        } finally {
            hideLoader();
        }
    }
}

function resetAnalysis() {
    // Hide results, show input
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset form
    resetForm();
    
    // Clear job ID
    currentJobId = null;
}

// UI Helper functions
function showLoader(message) {
    const loader = document.createElement('div');
    loader.id = 'export-loader';
    loader.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    `;
    loader.innerHTML = `
        <div style="background: white; padding: 30px; border-radius: 8px; text-align: center;">
            <div style="margin-bottom: 15px;">${message}</div>
            <div class="spinner" style="width: 40px; height: 40px; border: 4px solid #f3f4f6; border-top-color: #3b82f6; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
        </div>
        <style>
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        </style>
    `;
    document.body.appendChild(loader);
}

function hideLoader() {
    const loader = document.getElementById('export-loader');
    if (loader) {
        loader.remove();
    }
}

function showSuccess(message) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: #10b981;
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
