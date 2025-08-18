// Fact Checker Application JavaScript

// Global variables
let currentJobId = null;

document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const tabButtons = document.querySelectorAll('.tab-button');
    const inputPanels = document.querySelectorAll('.input-panel');
    
    tabButtons.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Update active states
            tabButtons.forEach(t => t.classList.remove('active'));
            inputPanels.forEach(p => p.classList.remove('active'));
            
            this.classList.add('active');
            document.getElementById(`${targetTab}-panel`).classList.add('active');
        });
    });
    
    // File upload
    const fileInput = document.getElementById('file-input');
    const fileDropZone = document.getElementById('file-drop-zone');
    
    if (fileDropZone) {
        fileDropZone.addEventListener('click', () => fileInput.click());
        
        fileDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileDropZone.classList.add('dragover');
        });
        
        fileDropZone.addEventListener('dragleave', () => {
            fileDropZone.classList.remove('dragover');
        });
        
        fileDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            fileDropZone.classList.remove('dragover');
            
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
    
    // Character counter
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    if (textInput && charCount) {
        textInput.addEventListener('input', function() {
            charCount.textContent = this.value.length.toLocaleString();
        });
    }
});

function updateFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    
    if (fileInfo && fileName) {
        fileName.textContent = file.name;
        fileInfo.style.display = 'flex';
    }
}

function removeFile() {
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    
    if (fileInput) fileInput.value = '';
    if (fileInfo) fileInfo.style.display = 'none';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function startAnalysis() {
    // Get the active input method
    const activePanel = document.querySelector('.input-panel.active');
    const method = activePanel.id.replace('-panel', '');
    
    let transcript = '';
    let source = '';
    
    try {
        // Get transcript based on method
        if (method === 'text') {
            transcript = document.getElementById('text-input').value.trim();
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
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
    
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
        
        // Store job ID
        currentJobId = data.job_id;
        
        // Start polling for results
        pollJobStatus(data.job_id);
        
    } catch (error) {
        console.error('Analysis error:', error);
        showError(error.message || 'Failed to analyze transcript');
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('input-section').style.display = 'block';
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
            updateProgress(data.progress || 0, data.message || 'Processing...');
            
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
            document.getElementById('progress-section').style.display = 'none';
            document.getElementById('input-section').style.display = 'block';
        }
    }, 5000); // Poll every 5 seconds
}

function updateProgress(percent, text) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressFill.style.width = percent + '%';
    progressText.textContent = text;
    
    // Update step indicators
    const steps = ['step-1', 'step-2', 'step-3', 'step-4'];
    const stepThresholds = [20, 40, 60, 90];
    
    steps.forEach((stepId, index) => {
        const step = document.getElementById(stepId);
        if (step) {
            if (percent >= stepThresholds[index]) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        }
    });
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
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('results-section').style.display = 'block';
        
    } catch (error) {
        console.error('Results error:', error);
        showError('Failed to load analysis results');
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('input-section').style.display = 'block';
    }
}

function displayResults(results) {
    // Update credibility score
    const score = results.credibility_score || 0;
    const pointer = document.getElementById('credibility-pointer');
    const scoreValue = document.getElementById('credibility-value');
    const scoreLabel = document.getElementById('credibility-label');
    
    if (pointer) pointer.style.left = `${score}%`;
    if (scoreValue) scoreValue.textContent = score;
    if (scoreLabel) scoreLabel.textContent = results.credibility_label || 'Unknown';
    
    // Update stats
    updateStats(results);
    
    // Display summary
    const summaryContainer = document.getElementById('analysis-summary');
    if (summaryContainer) {
        let summaryHtml = '';
        
        // Add speaker context if available
        if (results.speaker_context && results.speaker_context.speaker) {
            summaryHtml = generateSpeakerContextHTML(results.speaker_context);
        }
        
        // Add conversational summary
        summaryHtml += `
            <div class="conversational-summary">
                <p>We analyzed ${results.total_claims || 0} factual claims in this transcript. 
                ${results.true_claims || 0} were verified as true, 
                ${results.false_claims || 0} were found to be false, and 
                ${results.unverified_claims || 0} could not be verified.</p>
            </div>
        `;
        
        summaryContainer.innerHTML = summaryHtml;
    }
    
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
                            ${verdict.toUpperCase()}
                        </div>
                    </div>
                    ${check.explanation ? `
                        <div class="fact-check-details">
                            <p>${check.explanation}</p>
                            ${check.sources && check.sources.length > 0 ? `
                                <div class="fact-check-source">
                                    <strong>Sources:</strong> ${check.sources.join(', ')}
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }
        
        container.appendChild(item);
    });
}

function getVerdictClass(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = {
        'true': 'true',
        'mostly_true': 'true',
        'false': 'false',
        'mostly_false': 'false',
        'misleading': 'false',
        'deceptive': 'false',
        'mixed': 'mixed',
        'unverified': 'unverified',
        'unsubstantiated': 'unverified',
        'lacks_context': 'unverified'
    };
    return mapping[v] || 'unverified';
}

function getVerdictIcon(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = {
        'true': 'fa-check-circle',
        'mostly_true': 'fa-check-circle',
        'false': 'fa-times-circle',
        'mostly_false': 'fa-times-circle',
        'misleading': 'fa-exclamation-triangle',
        'deceptive': 'fa-exclamation-triangle',
        'mixed': 'fa-adjust',
        'unverified': 'fa-question-circle',
        'unsubstantiated': 'fa-question-circle',
        'lacks_context': 'fa-info-circle'
    };
    return mapping[v] || 'fa-question-circle';
}

function generateSpeakerContextHTML(context) {
    if (!context || !context.speaker) {
        return '';
    }
    
    let html = '<div class="speaker-context-section">';
    html += `<h4>About ${context.speaker}:</h4>`;
    
    // Criminal record
    if (context.criminal_record) {
        html += `<div class="alert alert-danger">
            <i class="fas fa-gavel"></i>
            <strong>Criminal Record:</strong> ${context.criminal_record}
        </div>`;
    }
    
    // Fraud history
    if (context.fraud_history) {
        html += `<div class="alert alert-warning">
            <i class="fas fa-dollar-sign"></i>
            <strong>Fraud History:</strong> ${context.fraud_history}
        </div>`;
    }
    
    // Fact-checking history
    if (context.fact_check_history) {
        const alertClass = context.fact_check_history.toLowerCase().includes('false') ? 
            'alert-warning' : 'alert-info';
        html += `<div class="alert ${alertClass}">
            <i class="fas fa-chart-line"></i>
            <strong>Fact-Check History:</strong> ${context.fact_check_history}
        </div>`;
    }
    
    // Credibility notes
    if (context.credibility_notes) {
        html += `<div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            <strong>Credibility Assessment:</strong> ${context.credibility_notes}
        </div>`;
    }
    
    html += '</div>';
    return html;
}

async function exportResults(format) {
    if (!currentJobId) {
        showError('No results to export');
        return;
    }
    
    showLoader('Generating PDF...');
    
    try {
        const response = await fetch(`/api/export/${currentJobId}/${format}`);
        
        if (response.ok) {
            // Create blob from response
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `fact-check-report-${currentJobId}.pdf`;
            
            // Trigger download
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('PDF downloaded successfully!');
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

function resetAnalysis() {
    // Hide results, show input
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset form
    resetForm();
    
    // Clear job ID
    currentJobId = null;
}

function resetForm() {
    // Clear text input
    document.getElementById('text-input').value = '';
    document.getElementById('char-count').textContent = '0';
    
    // Clear file input
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-name').textContent = '';
    
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
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    const icon = type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-times-circle' : 'fa-info-circle';
    notification.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
        <style>
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        </style>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        notification.style.animationFillMode = 'forwards';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
    
    // Add slide out animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}
