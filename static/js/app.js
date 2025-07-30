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
}

// Remove selected file
function removeFile() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-drop-zone').style.display = 'block';
}

// Start analysis
async function startAnalysis() {
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
            return;
        }
        analysisData.content = text;
        
    } else if (activeTab === 'youtube') {
        const url = document.getElementById('youtube-url').value.trim();
        if (!url) {
            alert('Please enter a YouTube URL.');
            return;
        }
        analysisData.url = url;
        
    } else if (activeTab === 'file') {
        const fileInput = document.getElementById('file-input');
        if (!fileInput.files.length) {
            alert('Please select a file to analyze.');
            return;
        }
        
        // For file upload, we need to use FormData
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('type', 'file');
        
        try {
            showProgress();
            
            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                currentJobId = result.job_id;
                pollJobStatus();
            } else {
                hideProgress();
                alert(result.error || 'Analysis failed.');
            }
        } catch (error) {
            hideProgress();
            alert('Error: ' + error.message);
        }
        return;
    }
    
    // For text and YouTube inputs
    try {
        showProgress();
        
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
            pollJobStatus();
        } else {
            hideProgress();
            alert(result.error || 'Analysis failed.');
        }
    } catch (error) {
        hideProgress();
        alert('Error: ' + error.message);
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

// Poll job status
function pollJobStatus() {
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const status = await response.json();
            
            updateProgress(status.progress);
            
            if (status.status === 'complete') {
                clearInterval(pollInterval);
                fetchResults();
            } else if (status.status === 'error') {
                clearInterval(pollInterval);
                hideProgress();
                alert('Analysis error: ' + (status.error || 'Unknown error'));
            }
        } catch (error) {
            clearInterval(pollInterval);
            hideProgress();
            alert('Error checking status: ' + error.message);
        }
    }, 1000);
}

// Update progress display
function updateProgress(progress) {
    document.getElementById('progress-fill').style.width = progress + '%';
    
    // Update progress text and steps
    const steps = document.querySelectorAll('.step');
    steps.forEach(step => step.classList.remove('active'));
    
    if (progress < 25) {
        document.getElementById('progress-text').textContent = 'Processing transcript...';
        document.getElementById('step-1').classList.add('active');
    } else if (progress < 50) {
        document.getElementById('progress-text').textContent = 'Extracting claims...';
        document.getElementById('step-2').classList.add('active');
    } else if (progress < 75) {
        document.getElementById('progress-text').textContent = 'Fact checking claims...';
        document.getElementById('step-3').classList.add('active');
    } else {
        document.getElementById('progress-text').textContent = 'Generating report...';
        document.getElementById('step-4').classList.add('active');
    }
}

// Fetch analysis results
async function fetchResults() {
    try {
        const response = await fetch(`/api/results/${currentJobId}`);
        const data = await response.json();
        
        if (data.success) {
            displayResults(data.results);
        } else {
            throw new Error(data.error || 'Failed to fetch results');
        }
    } catch (error) {
        hideProgress();
        alert('Error fetching results: ' + error.message);
    }
}

// Display analysis results
function displayResults(results) {
    // Hide progress, show results
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    // Update credibility meter
    const credibilityScore = results.credibility_score;
    document.getElementById('credibility-value').textContent = Math.round(credibilityScore);
    document.getElementById('credibility-label').textContent = results.credibility_label;
    
    // Position meter pointer
    const pointer = document.getElementById('credibility-pointer');
    pointer.style.left = `${credibilityScore}%`;
    
    // Update summary
    document.getElementById('analysis-summary').textContent = results.summary;
    
    // Update statistics
    document.getElementById('total-claims').textContent = results.checked_claims;
    
    // Count verdicts
    let verifiedCount = 0;
    let falseCount = 0;
    let unverifiedCount = 0;
    
    results.fact_checks.forEach(check => {
        const verdict = check.verdict.toLowerCase();
        if (verdict === 'true' || verdict === 'mostly_true') {
            verifiedCount++;
        } else if (verdict === 'false' || verdict === 'mostly_false') {
            falseCount++;
        } else {
            unverifiedCount++;
        }
    });
    
    document.getElementById('verified-claims').textContent = verifiedCount;
    document.getElementById('false-claims').textContent = falseCount;
    document.getElementById('unverified-claims').textContent = unverifiedCount;
    
    // Display fact checks
    displayFactChecks(results.fact_checks);
}

// Display individual fact checks
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    factChecks.forEach((check, index) => {
        const verdictClass = getVerdictClass(check.verdict);
        const verdictIcon = getVerdictIcon(check.verdict);
        
        const item = document.createElement('div');
        item.className = `fact-check-item ${verdictClass}`;
        
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-claim">${check.claim}</div>
                <div class="fact-check-verdict ${verdictClass}">
                    <i class="fas ${verdictIcon}"></i>
                    ${formatVerdict(check.verdict)}
                </div>
            </div>
            <div class="fact-check-details">
                <p>${check.explanation}</p>
                ${check.confidence ? `<p><strong>Confidence:</strong> ${check.confidence}%</p>` : ''}
            </div>
            ${check.url ? `
                <div class="fact-check-source">
                    Source: <a href="${check.url}" target="_blank">${check.publisher}</a>
                </div>
            ` : ''}
        `;
        
        container.appendChild(item);
    });
}

// Get verdict class for styling
function getVerdictClass(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    if (v === 'true' || v === 'mostly_true') return 'true';
    if (v === 'false' || v === 'mostly_false') return 'false';
    return 'unverified';
}

// Get verdict icon
function getVerdictIcon(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    if (v === 'true' || v === 'mostly_true') return 'fa-check-circle';
    if (v === 'false' || v === 'mostly_false') return 'fa-times-circle';
    return 'fa-question-circle';
}

// Format verdict for display
function formatVerdict(verdict) {
    return verdict.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Export results
async function exportResults(format) {
    try {
        const response = await fetch(`/api/export/${currentJobId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ format: format })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Download the file
            window.location.href = result.download_url;
        } else {
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
    document.getElementById('youtube-url').value = '';
    removeFile();
    
    // Reset UI
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset progress
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Initializing...';
}
