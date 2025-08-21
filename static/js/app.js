// Enhanced Fact Checker Frontend JavaScript

// Global variables
let currentJobId = null;
let pollInterval = null;

// Verdict display mappings
const VERDICT_MAPPINGS = {
    'true': { icon: '✓', class: 'verdict-true', label: 'True' },
    'mostly_true': { icon: '✓', class: 'verdict-mostly-true', label: 'Mostly True' },
    'nearly_true': { icon: '✓', class: 'verdict-nearly-true', label: 'Nearly True' },
    'exaggeration': { icon: '⚡', class: 'verdict-exaggeration', label: 'Exaggeration' },
    'misleading': { icon: '⚠️', class: 'verdict-misleading', label: 'Misleading' },
    'mostly_false': { icon: '✗', class: 'verdict-mostly-false', label: 'Mostly False' },
    'false': { icon: '✗', class: 'verdict-false', label: 'False' },
    'intentionally_deceptive': { icon: '🚨', class: 'verdict-intentionally-deceptive', label: 'Intentionally Deceptive' },
    'needs_context': { icon: '?', class: 'verdict-needs-context', label: 'Needs Context' },
    'opinion': { icon: '💭', class: 'verdict-opinion', label: 'Opinion' },
    'unverified': { icon: '?', class: 'verdict-unverified', label: 'Unverified' }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeFileInput();
    initializeForm();
    initializeExportButtons();
    initializeYouTubeInput();
});

// Tab functionality
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            // Update button states
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Update content visibility
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === targetTab) {
                    content.classList.add('active');
                }
            });
        });
    });
}

// File input handling
function initializeFileInput() {
    const fileInput = document.getElementById('file-input');
    const fileName = document.getElementById('file-name');
    
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                fileName.textContent = `Selected: ${file.name}`;
            } else {
                fileName.textContent = 'No file selected';
            }
        });
    }
}

// YouTube input handling
function initializeYouTubeInput() {
    const youtubeInput = document.getElementById('youtube-url');
    if (youtubeInput) {
        youtubeInput.placeholder = 'https://www.youtube.com/watch?v=...';
    }
}

// Form submission
function initializeForm() {
    const form = document.getElementById('fact-check-form');
    if (form) {
        form.addEventListener('submit', handleSubmit);
    }
}

async function handleSubmit(e) {
    e.preventDefault();
    
    // Get active tab
    const activeTab = document.querySelector('.tab-content.active');
    const sourceType = activeTab.id.replace('-input', '');
    
    // Create form data
    const formData = new FormData();
    formData.append('source_type', sourceType);
    
    // Add speech date if provided
    const speechDate = document.getElementById('speech-date');
    if (speechDate && speechDate.value) {
        formData.append('speech_date', speechDate.value);
    }
    
    // Add source-specific data
    if (sourceType === 'text') {
        const transcript = document.getElementById('transcript-text').value;
        if (!transcript.trim()) {
            showError('Please enter a transcript');
            return;
        }
        formData.append('transcript', transcript);
    } else if (sourceType === 'file') {
        const fileInput = document.getElementById('file-input');
        if (!fileInput.files[0]) {
            showError('Please select a file');
            return;
        }
        formData.append('file', fileInput.files[0]);
    } else if (sourceType === 'youtube') {
        const youtubeUrl = document.getElementById('youtube-url').value;
        if (!youtubeUrl.trim()) {
            showError('Please enter a YouTube URL');
            return;
        }
        formData.append('youtube_url', youtubeUrl);
    }
    
    // Show loading state
    showLoading();
    
    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentJobId = data.job_id;
            console.log('Analysis started with job ID:', currentJobId);
            console.log('Source:', sourceType);
            pollForResults();
        } else {
            hideLoading();
            showError(data.error || 'Analysis failed');
        }
    } catch (error) {
        hideLoading();
        showError('Network error: ' + error.message);
    }
}

// Poll for results
function pollForResults() {
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/status/${currentJobId}`);
            const status = await response.json();
            
            updateProgress(status);
            
            if (status.status === 'completed') {
                clearInterval(pollInterval);
                const resultsResponse = await fetch(`/results/${currentJobId}`);
                const results = await resultsResponse.json();
                hideLoading();
                displayResults(results);
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                hideLoading();
                showError(status.error || 'Analysis failed');
            }
        } catch (error) {
            clearInterval(pollInterval);
            hideLoading();
            showError('Failed to get status');
        }
    }, 1000);
}

// Update progress
function updateProgress(status) {
    const progressBar = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');
    
    if (progressBar && status.progress !== undefined) {
        progressBar.style.width = `${status.progress}%`;
    }
    
    if (progressText) {
        if (status.stage === 'extracting_claims') {
            progressText.textContent = 'Extracting claims...';
        } else if (status.checked_claims !== undefined) {
            progressText.textContent = `Checking claim ${status.checked_claims} of ${status.total_claims || '?'}`;
        } else {
            progressText.textContent = 'Processing...';
        }
    }
}

// Display results
function displayResults(results) {
    const resultsSection = document.getElementById('results-section');
    if (!resultsSection) return;
    
    resultsSection.style.display = 'block';
    resultsSection.innerHTML = `
        <div class="results-header">
            <h2>Fact Check Results</h2>
            <div class="export-buttons">
                <button class="btn btn-secondary export-btn" data-format="pdf">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                        <polyline points="10 9 9 9 8 9"></polyline>
                    </svg>
                    Export PDF
                </button>
                <button class="btn btn-secondary export-btn" data-format="json">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Export JSON
                </button>
                <button class="btn btn-secondary export-btn" data-format="text">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                        <line x1="16" y1="21" x2="8" y2="21"></line>
                    </svg>
                    Export Text
                </button>
            </div>
        </div>
        
        ${results.enhanced_summary ? `
            <div class="enhanced-summary">
                <h3>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                    Executive Summary
                </h3>
                <div class="summary-content">${formatSummary(results.enhanced_summary)}</div>
            </div>
        ` : ''}
        
        ${results.speakers && Object.keys(results.speakers).length > 0 ? displaySpeakerContext(results.speakers) : ''}
        
        ${results.patterns ? displayPatterns(results.patterns) : ''}
        
        ${displayCredibilityMeter(results)}
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${results.total_claims || results.checked_claims || 0}</div>
                <div class="stat-label">Total Claims</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${countVerdicts(results.fact_checks, ['true', 'mostly_true', 'nearly_true'])}</div>
                <div class="stat-label">True Claims</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${countVerdicts(results.fact_checks, ['false', 'mostly_false', 'intentionally_deceptive'])}</div>
                <div class="stat-label">False Claims</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${countVerdicts(results.fact_checks, ['misleading', 'exaggeration'])}</div>
                <div class="stat-label">Misleading</div>
            </div>
        </div>
        
        <h3 style="margin-top: 2rem; margin-bottom: 1rem;">Detailed Fact Checks</h3>
        <div class="fact-check-list">
            ${results.fact_checks.map((check, index) => displayFactCheck(check, index)).join('')}
        </div>
    `;
    
    // Re-initialize export buttons
    initializeExportButtons();
}

function displaySpeakerContext(speakers) {
    let html = '<div class="speaker-context">';
    html += '<h4><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> Speaker Background</h4>';
    html += '<div class="speaker-info">';
    
    for (const [speaker, context] of Object.entries(speakers)) {
        if (context.criminal_record || context.fraud_history) {
            html += '<div class="speaker-record">';
            html += `<strong>${speaker}:</strong>`;
            if (context.criminal_record) {
                html += `<span class="criminal-record">Criminal Record: ${context.criminal_record}</span>`;
            }
            if (context.fraud_history) {
                html += `<span class="fraud-history">Fraud History: ${context.fraud_history}</span>`;
            }
            html += '</div>';
        }
    }
    
    html += '</div></div>';
    return html;
}

function displayPatterns(patterns) {
    if (!patterns.deception_pattern) return '';
    
    return `
        <div class="pattern-alert">
            <svg class="pattern-alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            <div class="pattern-alert-content">
                <h4>Pattern of Deception Detected</h4>
                <p>This transcript contains ${patterns.false_claims} false claims, ${patterns.misleading_claims} misleading claims, and ${patterns.intentionally_deceptive} intentionally deceptive statements. This appears to be a deliberate pattern of misinformation.</p>
            </div>
        </div>
    `;
}

function displayCredibilityMeter(results) {
    const patterns = results.patterns || {};
    const percentage = 100 - (patterns.deceptive_percentage || 0);
    let level = 'high';
    let label = 'High Credibility';
    
    if (percentage < 50) {
        level = 'low';
        label = 'Low Credibility';
    } else if (percentage < 75) {
        level = 'medium';
        label = 'Medium Credibility';
    }
    
    return `
        <div class="credibility-meter">
            <h3>Overall Credibility Score</h3>
            <div class="meter-container">
                <div class="meter-fill ${level}" style="width: ${percentage}%">
                    <div class="meter-label">${Math.round(percentage)}%</div>
                </div>
            </div>
            <div class="meter-description">${label}</div>
        </div>
    `;
}

function displayFactCheck(check, index) {
    const verdict = check.verdict || 'unverified';
    const verdictInfo = VERDICT_MAPPINGS[verdict.toLowerCase()] || VERDICT_MAPPINGS.unverified;
    
    return `
        <div class="fact-check-item">
            ${check.ai_analysis_used ? '<div class="ai-badge">💡 AI Enhanced</div>' : ''}
            <div class="fact-check-header">
                <div class="claim-text">${check.claim || 'No claim text'}</div>
                <span class="verdict-badge ${verdictInfo.class}">
                    ${verdictInfo.icon} ${verdictInfo.label}
                </span>
            </div>
            
            ${check.full_context ? `
                <div class="full-context">
                    <strong>Full context:</strong> ${check.full_context}
                </div>
            ` : ''}
            
            <div class="explanation">${check.explanation || 'No explanation available'}</div>
            
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
                <div class="sources">
                    <h4>Sources</h4>
                    <div class="source-list">
                        ${check.sources.map(source => `
                            <span class="source-item">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                                </svg>
                                ${source}
                            </span>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

function formatSummary(summary) {
    return summary
        .replace(/🚨/g, '<span class="warning">🚨</span>')
        .replace(/⚠️/g, '<span class="warning">⚠️</span>')
        .replace(/✓/g, '<span class="success">✓</span>')
        .replace(/✅/g, '<span class="success">✅</span>')
        .replace(/❌/g, '<span class="warning">❌</span>')
        .replace(/💡/g, '<span class="success">💡</span>')
        .replace(/\n/g, '<br>');
}

function countVerdicts(factChecks, verdictTypes) {
    if (!factChecks) return 0;
    return factChecks.filter(check => 
        verdictTypes.includes((check.verdict || 'unverified').toLowerCase())
    ).length;
}

// Export functionality
function initializeExportButtons() {
    const exportButtons = document.querySelectorAll('.export-btn');
    exportButtons.forEach(button => {
        button.addEventListener('click', () => {
            const format = button.getAttribute('data-format');
            if (currentJobId) {
                exportResults(currentJobId, format);
            }
        });
    });
}

async function exportResults(jobId, format) {
    try {
        const response = await fetch(`/export/${jobId}/${format}`);
        
        if (response.ok) {
            if (format === 'json') {
                const data = await response.json();
                downloadJSON(data, `fact_check_${jobId}.json`);
            } else {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `fact_check_${jobId}.${format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }
        } else {
            showError('Export failed');
        }
    } catch (error) {
        showError('Export error: ' + error.message);
    }
}

function downloadJSON(data, filename) {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// Loading and error states
function showLoading() {
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <div class="loading-content">
                <h3>Analyzing Transcript</h3>
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <p class="progress-text">Starting analysis...</p>
            </div>
        </div>
    `;
    document.body.appendChild(loadingOverlay);
}

function hideLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.remove();
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        ${message}
    `;
    
    const container = document.querySelector('.main-content');
    if (container) {
        container.insertBefore(errorDiv, container.firstChild);
        setTimeout(() => errorDiv.remove(), 5000);
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Enhanced keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const form = document.getElementById('fact-check-form');
        if (form) {
            form.dispatchEvent(new Event('submit'));
        }
    }
    
    // Escape to close loading
    if (e.key === 'Escape') {
        hideLoading();
        if (pollInterval) {
            clearInterval(pollInterval);
        }
    }
});

// Auto-save transcript
const transcriptTextarea = document.getElementById('transcript-text');
if (transcriptTextarea) {
    const saveTranscript = debounce(() => {
        localStorage.setItem('saved-transcript', transcriptTextarea.value);
    }, 1000);
    
    transcriptTextarea.addEventListener('input', saveTranscript);
    
    // Restore saved transcript on load
    const savedTranscript = localStorage.getItem('saved-transcript');
    if (savedTranscript) {
        transcriptTextarea.value = savedTranscript;
    }
}

// Example transcript button
function loadExampleTranscript() {
    const transcriptTextarea = document.getElementById('transcript-text');
    if (transcriptTextarea) {
        transcriptTextarea.value = `Speaker 1: The unemployment rate has dropped to 3.5%, the lowest in 50 years.

Speaker 2: Actually, while the rate is low, we've seen similar rates multiple times in the past 50 years, including in 2019.

Speaker 1: Crime rates in major cities have increased by 40% this year compared to last year.

Speaker 2: That's an exaggeration. FBI data shows violent crime increased by about 5% nationally, though some cities did see larger increases.

Speaker 1: We've invested more in renewable energy than any previous administration - over $100 billion last year alone.

Speaker 2: I'd need to verify those specific numbers, but renewable energy investment has indeed increased significantly.`;
        
        // Switch to text tab
        document.querySelector('[data-tab="text-input"]').click();
    }
}

// Add example button to UI
document.addEventListener('DOMContentLoaded', function() {
    const textTab = document.getElementById('text-input');
    if (textTab) {
        const exampleBtn = document.createElement('button');
        exampleBtn.type = 'button';
        exampleBtn.className = 'btn btn-secondary';
        exampleBtn.style.marginBottom = '1rem';
        exampleBtn.innerHTML = 'Load Example Transcript';
        exampleBtn.onclick = loadExampleTranscript;
        textTab.insertBefore(exampleBtn, textTab.firstChild);
    }
});
