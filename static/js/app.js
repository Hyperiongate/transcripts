// Transcript Fact Checker - Main JavaScript

// Enhanced verdict handling with clearer language
const VERDICT_MAPPINGS = {
    'true': { class: 'true', icon: 'fa-check-circle', label: 'True' },
    'mostly_true': { class: 'true', icon: 'fa-check-circle', label: 'Mostly True' },
    'mixed': { class: 'mixed', icon: 'fa-adjust', label: 'Mixed' },
    'misleading': { class: 'deceptive', icon: 'fa-exclamation-triangle', label: 'Deceptive' },
    'deceptive': { class: 'deceptive', icon: 'fa-exclamation-triangle', label: 'Deceptive' },
    'lacks_context': { class: 'lacks_context', icon: 'fa-info-circle', label: 'Lacks Critical Context' },
    'unsubstantiated': { class: 'unsubstantiated', icon: 'fa-question-circle', label: 'Unsubstantiated' },
    'mostly_false': { class: 'false', icon: 'fa-times-circle', label: 'Mostly False' },
    'false': { class: 'false', icon: 'fa-times-circle', label: 'False' },
    'unverified': { class: 'unverified', icon: 'fa-question-circle', label: 'Unverified' }
};

// Global variables
let currentJobId = null;
let pollInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeFileUpload();
    initializeTextInput();
    initializeYouTubeInput();
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

// YouTube input validation and formatting
function initializeYouTubeInput() {
    const youtubeInput = document.getElementById('youtube-url');
    
    if (!youtubeInput) {
        console.warn('YouTube input element not found');
        return;
    }
    
    // Add placeholder examples
    youtubeInput.placeholder = 'https://www.youtube.com/watch?v=... or https://youtu.be/...';
    
    // Auto-format YouTube URLs
    youtubeInput.addEventListener('paste', (e) => {
        setTimeout(() => {
            const url = youtubeInput.value.trim();
            if (url && isValidYouTubeUrl(url)) {
                youtubeInput.style.borderColor = '#10b981'; // Green border for valid
            } else if (url) {
                youtubeInput.style.borderColor = '#ef4444'; // Red border for invalid
            }
        }, 100);
    });
    
    youtubeInput.addEventListener('input', () => {
        const url = youtubeInput.value.trim();
        if (url && isValidYouTubeUrl(url)) {
            youtubeInput.style.borderColor = '#10b981';
        } else if (url) {
            youtubeInput.style.borderColor = '#ef4444';
        } else {
            youtubeInput.style.borderColor = '#e5e7eb'; // Default
        }
    });
}

// Validate YouTube URL
function isValidYouTubeUrl(url) {
    const patterns = [
        /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|m\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
        /^[a-zA-Z0-9_-]{11}$/ // Just video ID
    ];
    
    return patterns.some(pattern => pattern.test(url));
}

// Extract YouTube video ID
function extractVideoId(url) {
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|m\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
        /^([a-zA-Z0-9_-]{11})$/ // Just video ID
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
            return match[1];
        }
    }
    
    return null;
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

// Start analysis
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
            analysisData.content = text;
            
        } else if (activeTab === 'youtube') {
            const url = document.getElementById('youtube-url').value.trim();
            if (!url) {
                alert('Please enter a YouTube URL.');
                analyzeButton.disabled = false;
                return;
            }
            
            // Validate YouTube URL
            if (!isValidYouTubeUrl(url)) {
                alert('Please enter a valid YouTube URL.\n\nExamples:\n- https://www.youtube.com/watch?v=VIDEO_ID\n- https://youtu.be/VIDEO_ID\n- Just the video ID');
                analyzeButton.disabled = false;
                return;
            }
            
            // Show video ID for confirmation
            const videoId = extractVideoId(url);
            if (videoId) {
                console.log('Extracting transcript for video ID:', videoId);
            }
            
            analysisData.url = url;
            
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
        
        // For text and YouTube inputs
        try {
            showProgress();
            
            if (activeTab === 'youtube') {
                updateProgressMessage('Extracting YouTube transcript...');
            } else {
                updateProgressMessage('Processing text...');
            }
            
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
    document.getElementById('credibility-label').textContent = getCredibilityLabel(score);
    
    // Update credibility meter pointer
    const pointer = document.getElementById('credibility-pointer');
    const rotation = (score / 100) * 180 - 90; // -90 to 90 degrees
    pointer.style.transform = `rotate(${rotation}deg)`;
    
    // Update summary
    document.getElementById('analysis-summary').textContent = data.summary || 'Analysis complete.';
    
    // Update statistics
    const stats = data.statistics || {};
    document.getElementById('total-claims').textContent = stats.total_claims || 0;
    document.getElementById('verified-claims').textContent = stats.verified || 0;
    document.getElementById('false-claims').textContent = stats.false || 0;
    document.getElementById('unverified-claims').textContent = stats.unverified || 0;
    
    // Display fact checks
    displayFactChecks(data.fact_checks || []);
}

// Get credibility label based on score
function getCredibilityLabel(score) {
    if (score >= 80) return 'Highly Credible';
    if (score >= 60) return 'Moderately Credible';
    if (score >= 40) return 'Low Credibility';
    return 'Very Low Credibility';
}

// Display individual fact checks
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
        const verdictClass = getVerdictClass(verdict);
        const verdictIcon = getVerdictIcon(verdict);
        const verdictLabel = formatVerdict(verdict);
        
        item.innerHTML = `
            <div class="fact-check-header">
                <span class="fact-check-number">#${index + 1}</span>
                <span class="fact-check-verdict ${verdictClass}">
                    <i class="fas ${verdictIcon}"></i>
                    ${verdictLabel}
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

// Get verdict class for styling
function getVerdictClass(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.class : 'unverified';
}

// Get verdict icon
function getVerdictIcon(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.icon : 'fa-question-circle';
}

// Format verdict for display
function formatVerdict(verdict) {
    if (!verdict) return 'Unverified';
    
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.label : verdict.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Export results
async function exportResults(format) {
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
            body: JSON.stringify({ format: format })
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
    document.getElementById('youtube-url').value = '';
    document.getElementById('youtube-url').style.borderColor = '#e5e7eb';
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
