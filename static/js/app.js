// Transcript Fact Checker - Main JavaScript

// Enhanced verdict handling with clearer language (from enhanced.js)
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

// YouTube input validation and formatting
function initializeYouTubeInput() {
    const youtubeInput = document.getElementById('youtube-url');
    
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
                return;
            }
            if (text.length < 50) {
                alert('Please enter at least 50 characters of text.');
                return;
            }
            if (text.length > 50000) {
                alert('Text is too long. Maximum 50,000 characters allowed.');
                return;
            }
            analysisData.content = text;
            
        } else if (activeTab === 'youtube') {
            const url = document.getElementById('youtube-url').value.trim();
            if (!url) {
                alert('Please enter a YouTube URL.');
                return;
            }
            
            // Validate YouTube URL
            if (!isValidYouTubeUrl(url)) {
                alert('Please enter a valid YouTube URL.\n\nExamples:\n- https://www.youtube.com/watch?v=VIDEO_ID\n- https://youtu.be/VIDEO_ID\n- Just the video ID');
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
    document.getElementById('progress-fill').style.width = progress + '%';
    
    // Update steps
    const steps = document.querySelectorAll('.step');
    steps.forEach(step => step.classList.remove('active'));
    
    if (progress < 25) {
        document.getElementById('step-1').classList.add('active');
    } else if (progress < 50) {
        document.getElementById('step-2').classList.add('active');
    } else if (progress < 75) {
        document.getElementById('step-3').classList.add('active');
    } else {
        document.getElementById('step-4').classList.add('active');
    }
}

// Fetch analysis results
async function fetchResults() {
    try {
        updateProgressMessage('Loading results...');
        
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
    const credibilityScore = results.credibility_score || 0;
    document.getElementById('credibility-value').textContent = Math.round(credibilityScore);
    document.getElementById('credibility-label').textContent = results.credibility_label || 'Unknown';
    
    // Position meter pointer
    const pointer = document.getElementById('credibility-pointer');
    pointer.style.left = `${credibilityScore}%`;
    
    // Build comprehensive summary HTML
    let summaryHtml = '';
    
    // SPEAKER CONTEXT SECTION - Criminal record, fraud history, etc.
    if (results.speaker_context && results.speaker_context.speaker) {
        const context = results.speaker_context;
        
        summaryHtml += '<div class="speaker-context-section">';
        summaryHtml += `<h4>About ${context.speaker}:</h4>`;
        
        // Criminal record
        if (context.criminal_record) {
            summaryHtml += `<div class="alert alert-danger">
                <strong>⚖️ Criminal Record:</strong> ${context.criminal_record}
            </div>`;
        }
        
        // Fraud history
        if (context.fraud_history) {
            summaryHtml += `<div class="alert alert-warning">
                <strong>💰 Fraud History:</strong> ${context.fraud_history}
            </div>`;
        }
        
        // Fact-checking history
        if (context.fact_check_history) {
            summaryHtml += `<p><strong>📊 Fact-Check History:</strong> ${context.fact_check_history}</p>`;
        }
        
        // Legal issues
        if (context.legal_issues && context.legal_issues.length > 0) {
            summaryHtml += '<p><strong>⚡ Legal Issues:</strong></p><ul>';
            context.legal_issues.forEach(issue => {
                summaryHtml += `<li>${issue}</li>`;
            });
            summaryHtml += '</ul>';
        }
        
        summaryHtml += '</div>';
        summaryHtml += '<hr>';
    }
    
    // Show source information prominently for YouTube videos
    if (results.source && results.source.includes('YouTube')) {
        summaryHtml += `<div class="source-info"><strong>Source:</strong> ${results.source}</div>`;
    }
    
    // CONVERSATIONAL SUMMARY
    if (results.conversational_summary) {
        summaryHtml += `<div class="conversational-summary">
            <h4>Summary:</h4>
            <p>${results.conversational_summary}</p>
        </div>`;
    } else if (results.summary) {
        summaryHtml += `<p>${results.summary}</p>`;
    }
    
    // SPEAKERS AND TOPICS
    if (results.speakers && results.speakers.length > 0) {
        summaryHtml += `<div class="speaker-info"><strong>Speakers Identified:</strong> ${results.speakers.slice(0, 5).join(', ')}</div>`;
    }
    
    if (results.topics && results.topics.length > 0) {
        summaryHtml += `<div class="topic-info"><strong>Key Topics:</strong> ${results.topics.join(', ')}</div>`;
    }
    
    // SPEAKER HISTORY
    if (results.speaker_history) {
        const history = results.speaker_history;
        summaryHtml += '<div class="speaker-history">';
        summaryHtml += `<h4>Speaker Track Record:</h4>`;
        
        if (history.total_analyses > 1) {
            summaryHtml += `<p><strong>Previous Analyses:</strong> ${history.total_analyses}</p>`;
            summaryHtml += `<p><strong>Average Credibility:</strong> ${history.average_credibility.toFixed(0)}%</p>`;
            
            if (history.patterns && history.patterns.length > 0) {
                summaryHtml += '<p><strong>Patterns:</strong></p><ul>';
                history.patterns.forEach(pattern => {
                    summaryHtml += `<li>${pattern}</li>`;
                });
                summaryHtml += '</ul>';
            }
        }
        
        summaryHtml += '</div>';
    }
    
    // ANALYSIS NOTES (for demo mode)
    if (results.analysis_notes && results.analysis_notes.length > 0) {
        summaryHtml += '<div class="analysis-notes"><h4>Important Notes:</h4><ul>';
        results.analysis_notes.forEach(note => {
            summaryHtml += `<li>${note}</li>`;
        });
        summaryHtml += '</ul></div>';
    }
    
    document.getElementById('analysis-summary').innerHTML = summaryHtml;
    
    // Update statistics
    document.getElementById('total-claims').textContent = results.checked_claims || 0;
    
    // Count verdicts
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
    
    document.getElementById('verified-claims').textContent = verifiedCount;
    document.getElementById('false-claims').textContent = falseCount;
    document.getElementById('unverified-claims').textContent = unverifiedCount;
    
    // Display fact checks with enhanced dropdowns
    if (results.fact_checks && results.fact_checks.length > 0) {
        displayFactChecks(results.fact_checks);
    } else {
        document.getElementById('fact-check-list').innerHTML = '<p>No fact checks available.</p>';
    }
}

// Display individual fact checks with expandable dropdowns
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    factChecks.forEach((check, index) => {
        const verdict = check.verdict.toLowerCase().replace(' ', '_');
        const verdictInfo = VERDICT_MAPPINGS[verdict] || VERDICT_MAPPINGS['unverified'];
        
        const item = document.createElement('div');
        item.className = `fact-check-item ${verdictInfo.class}`;
        
        const itemId = `fact-check-${index}`;
        
        // Use full_context if available, otherwise use claim
        const claimText = check.full_context || check.claim;
        const claimSnippet = claimText.length > 150 ? 
            claimText.substring(0, 150) + '...' : claimText;
        
        // Check if this is a demo result
        const isDemoMode = check.explanation && check.explanation.includes('[DEMO MODE]');
        const demoBadge = isDemoMode ? '<span class="demo-badge">DEMO</span>' : '';
        
        // Create meaningful explanation text for special verdicts
        let detailsHtml = '';
        
        // For "lacks critical context", explain WHAT context is missing
        if (verdict === 'lacks_context' || verdict === 'lacks_critical_context') {
            detailsHtml = `
                <div class="explanation-section">
                    <h4>Why This Lacks Context:</h4>
                    <p>${check.explanation}</p>
                    ${check.missing_context ? `
                        <div class="missing-context-box">
                            <strong>Missing Context:</strong> ${check.missing_context}
                        </div>
                    ` : ''}
                </div>
            `;
        } else if (verdict === 'deceptive' || verdict === 'misleading') {
            detailsHtml = `
                <div class="explanation-section">
                    <h4>Why This Is Deceptive:</h4>
                    <p>${check.explanation}</p>
                </div>
            `;
        } else {
            detailsHtml = `
                <div class="explanation-section">
                    <h4>Explanation:</h4>
                    <p>${check.explanation || 'No explanation available'}</p>
                </div>
            `;
        }
        
        item.innerHTML = `
            <div class="fact-check-header" onclick="toggleFactCheck('${itemId}')">
                <div class="fact-check-claim">
                    <i class="fas fa-chevron-right toggle-icon" id="${itemId}-icon"></i>
                    ${claimSnippet}
                </div>
                <div class="fact-check-verdict ${verdictInfo.class}">
                    <i class="fas ${verdictInfo.icon}"></i>
                    ${verdictInfo.label}
                    ${demoBadge}
                </div>
            </div>
            <div class="fact-check-details-wrapper" id="${itemId}" style="display: none;">
                <div class="fact-check-details">
                    <div class="original-text-section">
                        <h4>Full Claim</h4>
                        <p class="original-text">"${claimText}"</p>
                    </div>
                    
                    ${detailsHtml}
                    
                    ${check.context_note ? `
                    <div class="context-resolution">
                        <h4>Context Resolution</h4>
                        <p>${check.context_note}</p>
                    </div>
                    ` : ''}
                    
                    ${check.analysis ? `
                    <div class="analysis-section">
                        <h4>Detailed Analysis</h4>
                        <p>${check.analysis}</p>
                    </div>
                    ` : ''}
                    
                    ${check.context ? `
                    <div class="context-section">
                        <h4>Important Context</h4>
                        <p>${check.context}</p>
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
                    
                    ${check.sources && check.sources.length > 0 ? `
                    <div class="sources-section">
                        <h4>Sources Consulted</h4>
                        <ul>
                            ${check.sources.map(source => `<li>${source}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}
                    
                    ${check.source_breakdown ? `
                    <div class="source-breakdown">
                        <h4>Source Types Used</h4>
                        <ul>
                            ${Object.entries(check.source_breakdown).map(([type, count]) => 
                                `<li>${type}: ${count}</li>`
                            ).join('')}
                        </ul>
                    </div>
                    ` : ''}
                    
                    ${check.url ? `
                    <div class="primary-source">
                        <h4>Primary Source</h4>
                        <a href="${check.url}" target="_blank" rel="noopener">
                            <i class="fas fa-external-link-alt"></i>
                            ${check.publisher || 'View Source'}
                        </a>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Toggle fact check dropdown
function toggleFactCheck(itemId) {
    const details = document.getElementById(itemId);
    const icon = document.getElementById(`${itemId}-icon`);
    
    if (details.style.display === 'none') {
        // Close all other dropdowns first
        document.querySelectorAll('.fact-check-details-wrapper').forEach(el => {
            el.style.display = 'none';
        });
        document.querySelectorAll('.toggle-icon').forEach(el => {
            el.classList.remove('fa-chevron-down');
            el.classList.add('fa-chevron-right');
        });
        
        // Open this dropdown
        details.style.display = 'block';
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');
        
        // Smooth scroll to view
        details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
        details.style.display = 'none';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-right');
    }
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

// Export results as PDF only
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
function resetAnalysis() {
    currentJobId = null;
    
    // Clear inputs
    document.getElementById('text-input').value = '';
    document.getElementById('youtube-url').value = '';
    document.getElementById('youtube-url').style.borderColor = '#e5e7eb';
    removeFile();
    
    // Reset UI
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    
    // Reset progress
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Initializing...';
    
    // Clear any intervals
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// CSS styles are now in main.css and enhanced.css - no need for JavaScript injection
