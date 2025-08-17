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
    
    if (!dropZone || !fileInput) return;
    
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
    
    if (!textInput || !charCount) return;
    
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
window.removeFile = function() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-drop-zone').style.display = 'block';
}

// Start analysis
window.startAnalysis = async function() {
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
            analysisData.content = text;
            
        } else if (activeTab === 'file') {
            const fileInput = document.getElementById('file-input');
            if (!fileInput.files.length) {
                alert('Please select a file to analyze.');
                analyzeButton.disabled = false;
                return;
            }
            
            // For file upload, we need to use FormData
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('type', 'file');
            
            try {
                showProgress();
                updateProgressMessage('Uploading file...');
                
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData
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
    const progressText = document.getElementById('progress-text');
    if (progressText) {
        progressText.textContent = message;
    }
}

// Poll job status
function pollJobStatus() {
    let errorCount = 0;
    const maxErrors = 5;
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const status = await response.json();
            
            if (status.error && response.status === 404) {
                clearInterval(pollInterval);
                hideProgress();
                alert('Job not found. Please try again.');
                return;
            }
            
            updateProgress(status.progress || 0);
            
            // Update message based on status
            if (status.status === 'processing') {
                updateProgressMessage('Processing transcript...');
            } else if (status.status === 'fact_checking') {
                updateProgressMessage('Fact checking claims...');
            } else if (status.status === 'generating_report') {
                updateProgressMessage('Generating report...');
            }
            
            if (status.status === 'complete') {
                clearInterval(pollInterval);
                fetchResults();
            } else if (status.status === 'error') {
                clearInterval(pollInterval);
                hideProgress();
                alert('Analysis error: ' + (status.error || 'Unknown error'));
            }
            
            // Reset error count on successful request
            errorCount = 0;
            
        } catch (error) {
            errorCount++;
            console.error('Error checking status:', error);
            
            if (errorCount >= maxErrors) {
                clearInterval(pollInterval);
                hideProgress();
                alert('Error checking status: ' + error.message);
            }
        }
    }, 1000);
}

// Update progress display
function updateProgress(progress) {
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) {
        progressFill.style.width = progress + '%';
    }
    
    // Update steps
    const steps = document.querySelectorAll('.step');
    steps.forEach(step => step.classList.remove('active'));
    
    if (progress < 25) {
        const step1 = document.getElementById('step-1');
        if (step1) step1.classList.add('active');
    } else if (progress < 50) {
        const step2 = document.getElementById('step-2');
        if (step2) step2.classList.add('active');
    } else if (progress < 75) {
        const step3 = document.getElementById('step-3');
        if (step3) step3.classList.add('active');
    } else {
        const step4 = document.getElementById('step-4');
        if (step4) step4.classList.add('active');
    }
}

// Fetch analysis results
async function fetchResults() {
    try {
        updateProgressMessage('Loading results...');
        
        const response = await fetch(`/api/results/${currentJobId}`);
        const data = await response.json();
        
        if (data.success) {
            // Use the global displayResults function from enhanced.js
            if (window.displayResults) {
                window.displayResults(data.results);
            } else {
                console.error('displayResults function not found');
                hideProgress();
                alert('Error displaying results. Please refresh the page.');
            }
        } else {
            throw new Error(data.error || 'Failed to fetch results');
        }
    } catch (error) {
        hideProgress();
        alert('Error fetching results: ' + error.message);
    }
}

// Export results as PDF only
window.exportResults = async function(format) {
    if (!currentJobId) {
        alert('No results to export');
        return;
    }
    
    try {
        const response = await fetch(`/api/export/${currentJobId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ format: 'pdf' })  // Always PDF
        });
        
        if (response.ok) {
            // Create a blob from the response
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `fact-check-report-${new Date().toISOString().split('T')[0]}.pdf`;
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
window.resetAnalysis = function() {
    currentJobId = null;
    
    // Clear inputs
    const textInput = document.getElementById('text-input');
    if (textInput) textInput.value = '';
    
    const charCount = document.getElementById('char-count');
    if (charCount) charCount.textContent = '0';
    
    removeFile();
    
    // Reset UI
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset progress
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) progressFill.style.width = '0%';
    
    const progressText = document.getElementById('progress-text');
    if (progressText) progressText.textContent = 'Initializing...';
    
    // Clear any intervals
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}
