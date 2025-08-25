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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tabs
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
    
    // Character counter
    const textInput = document.getElementById('text-input');
    const charCount = document.getElementById('char-count');
    
    if (textInput) {
        textInput.addEventListener('input', () => {
            charCount.textContent = textInput.value.length;
            
            // Warn if approaching limit
            if (textInput.value.length > 45000) {
                charCount.style.color = '#ef4444';
            } else {
                charCount.style.color = '#6b7280';
            }
        });
    }
    
    // YouTube input handler
    const youtubeInput = document.getElementById('youtube-url');
    if (youtubeInput) {
        youtubeInput.addEventListener('paste', (e) => {
            setTimeout(() => {
                validateYouTubeUrl(e.target.value);
            }, 100);
        });
    }
});

// Validate YouTube URL
function validateYouTubeUrl(url) {
    const regex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/;
    const match = url.match(regex);
    
    const errorDiv = document.getElementById('youtube-error');
    const submitBtn = document.querySelector('.submit-button');
    
    if (match) {
        errorDiv.style.display = 'none';
        submitBtn.disabled = false;
        return match[1];
    } else if (url.length > 0) {
        errorDiv.style.display = 'block';
        errorDiv.textContent = 'Please enter a valid YouTube URL';
        submitBtn.disabled = true;
        return null;
    }
}

// Submit transcript for analysis
async function analyzeTranscript() {
    const activePanel = document.querySelector('.input-panel.active');
    const tabType = activePanel.id.replace('-panel', '');
    
    let transcript = '';
    
    if (tabType === 'text') {
        transcript = document.getElementById('text-input').value;
        if (!transcript.trim()) {
            showError('Please enter a transcript to analyze');
            return;
        }
    } else if (tabType === 'youtube') {
        const url = document.getElementById('youtube-url').value;
        const videoId = validateYouTubeUrl(url);
        if (!videoId) {
            showError('Please enter a valid YouTube URL');
            return;
        }
        
        // TODO: Implement YouTube transcript extraction
        showError('YouTube feature coming soon!');
        return;
    }
    
    // Show loading state
    showLoading();
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ transcript: transcript })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Start polling for results
        pollForResults();
        
    } catch (error) {
        hideLoading();
        showError('Error starting analysis: ' + error.message);
    }
}

// Poll for job results
function pollForResults() {
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            const data = await response.json();
            
            // Update progress
            updateProgress(data.progress || 0, data.message || 'Processing...');
            
            if (data.status === 'completed') {
                clearInterval(pollInterval);
                const resultsResponse = await fetch(`/api/results/${currentJobId}`);
                const results = await resultsResponse.json();
                displayResults(results);
                hideLoading();
            } else if (data.status === 'failed') {
                clearInterval(pollInterval);
                hideLoading();
                showError('Analysis failed: ' + (data.error || 'Unknown error'));
            }
            
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoading();
                showError('Analysis timed out. Please try again.');
            }
            
        } catch (error) {
            clearInterval(pollInterval);
            hideLoading();
            showError('Error checking status: ' + error.message);
        }
    }, 1000); // Poll every second
}

// Display results with enhanced visuals
function displayResults(results) {
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    // Display enhanced summary with markdown support
    const summaryElement = document.getElementById('summary-text');
    const summary = results.summary || 'No summary available';
    
    // Convert markdown to HTML
    let summaryHtml = summary
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/🟢/g, '<span class="score-icon green">🟢</span>')
        .replace(/🟡/g, '<span class="score-icon yellow">🟡</span>')
        .replace(/🟠/g, '<span class="score-icon orange">🟠</span>')
        .replace(/🔴/g, '<span class="score-icon red">🔴</span>')
        .replace(/⚪/g, '<span class="score-icon white">⚪</span>');
    
    summaryElement.innerHTML = summaryHtml;
    
    // Update statistics with proper mapping
    const breakdown = results.credibility_score?.breakdown || {};
    document.getElementById('verified-true-count').textContent = breakdown.verified_true || 0;
    document.getElementById('verified-false-count').textContent = breakdown.verified_false || 0;
    document.getElementById('partially-accurate-count').textContent = breakdown.partially_accurate || 0;
    document.getElementById('unverifiable-count').textContent = breakdown.unverifiable || 0;
    
    // Add visual indicators for rhetoric if present
    if (breakdown.empty_rhetoric > 0) {
        addRhetoricIndicator(breakdown.empty_rhetoric);
    }
    
    // Display fact checks with enhanced visuals
    displayFactChecks(results.fact_checks || []);
    
    // Display speaker analysis if available
    if (results.speaker_analysis && Object.keys(results.speaker_analysis).length > 0) {
        displaySpeakerAnalysis(results.speaker_analysis);
    }
    
    // Add credibility score visual
    displayCredibilityScore(results.credibility_score);
}

// Add rhetoric indicator to statistics
function addRhetoricIndicator(count) {
    const statsContainer = document.querySelector('.statistics-grid');
    if (statsContainer) {
        const rhetoricCard = document.createElement('div');
        rhetoricCard.className = 'stat-card rhetoric';
        rhetoricCard.innerHTML = `
            <div class="stat-number" style="color: #94a3b8;">${count}</div>
            <div class="stat-label">Empty Rhetoric</div>
            <div class="stat-icon">💨</div>
        `;
        statsContainer.appendChild(rhetoricCard);
    }
}

// Display credibility score with visual flair
function displayCredibilityScore(credScore) {
    if (!credScore) return;
    
    const score = credScore.score || 0;
    const label = credScore.label || 'Unknown';
    
    // Create visual score display
    const scoreContainer = document.createElement('div');
    scoreContainer.className = 'credibility-score-display';
    scoreContainer.innerHTML = `
        <div class="score-circle ${getScoreClass(score)}">
            <div class="score-value">${score}</div>
            <div class="score-label">/ 100</div>
        </div>
        <div class="score-assessment">${label}</div>
        <div class="score-bar">
            <div class="score-fill" style="width: ${score}%; background: ${getScoreColor(score)};"></div>
        </div>
    `;
    
    // Insert after summary
    const summarySection = document.querySelector('.summary-section');
    if (summarySection) {
        summarySection.appendChild(scoreContainer);
    }
}

// Display fact checks with enhanced formatting
function displayFactChecks(factChecks) {
    const container = document.getElementById('fact-checks-container');
    container.innerHTML = '';
    
    if (factChecks.length === 0) {
        container.innerHTML = '<p class="no-claims">No claims found to fact-check.</p>';
        return;
    }
    
    // Filter out null results
    const validFactChecks = factChecks.filter(fc => fc !== null);
    
    validFactChecks.forEach((check, index) => {
        const item = document.createElement('div');
        const verdictInfo = VERDICT_MAPPINGS[check.verdict] || VERDICT_MAPPINGS['unverifiable'];
        
        item.className = `fact-check-item verdict-${verdictInfo.class}`;
        
        // Add special styling for empty rhetoric
        if (check.verdict === 'empty_rhetoric') {
            item.classList.add('empty-rhetoric');
        }
        
        item.innerHTML = `
            <div class="fact-check-header">
                <div class="fact-check-number">#${index + 1}</div>
                <div class="fact-check-verdict" style="background-color: ${verdictInfo.color}">
                    <i class="fas ${verdictInfo.icon}"></i>
                    ${verdictInfo.label}
                </div>
                ${check.speaker && check.speaker !== 'Unknown' ? 
                    `<div class="fact-check-speaker">
                        <i class="fas fa-user"></i> ${check.speaker}
                    </div>` : ''}
            </div>
            <div class="fact-check-content">
                <p class="fact-check-claim">"${escapeHtml(check.claim || check.text || '')}"</p>
                <div class="fact-check-explanation">
                    ${formatExplanation(check.explanation || 'No explanation available.')}
                </div>
                ${check.confidence ? 
                    `<div class="confidence-indicator">
                        <span class="confidence-label">Confidence:</span>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${check.confidence}%"></div>
                        </div>
                        <span class="confidence-value">${check.confidence}%</span>
                    </div>` : ''}
                ${check.sources && check.sources.length > 0 ?
                    `<div class="fact-check-sources">
                        <i class="fas fa-link"></i> Sources: ${check.sources.join(', ')}
                    </div>` : ''}
            </div>
        `;
        
        container.appendChild(item);
    });
}

// Format explanation with better structure
function formatExplanation(explanation) {
    return explanation
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/PATTERN DETECTED:/g, '<span class="pattern-alert">⚠️ PATTERN DETECTED:</span>')
        .replace(/CONCLUSION:/g, '<strong>CONCLUSION:</strong>')
        .replace(/CONTEXT AND BALANCE:/g, '<strong>CONTEXT AND BALANCE:</strong>')
        .replace(/SPEAKER TRACK RECORD:/g, '<strong>SPEAKER TRACK RECORD:</strong>');
}

// Display speaker analysis
function displaySpeakerAnalysis(speakerAnalysis) {
    const container = document.getElementById('speaker-analysis');
    if (!container) return;
    
    container.innerHTML = '<h2>Speaker Analysis</h2>';
    
    Object.entries(speakerAnalysis).forEach(([speaker, data]) => {
        const speakerCard = document.createElement('div');
        speakerCard.className = 'speaker-card';
        
        const accuracy = (data.true_claims / data.total_claims * 100).toFixed(1);
        
        speakerCard.innerHTML = `
            <h3>${speaker}</h3>
            <div class="speaker-stats">
                <div class="stat">
                    <span class="stat-label">Total Claims:</span>
                    <span class="stat-value">${data.total_claims}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Accuracy Rate:</span>
                    <span class="stat-value ${accuracy >= 70 ? 'good' : accuracy >= 50 ? 'medium' : 'poor'}">${accuracy}%</span>
                </div>
                ${data.false_claims > 0 ? `
                <div class="stat">
                    <span class="stat-label">False Claims:</span>
                    <span class="stat-value poor">${data.false_claims}</span>
                </div>` : ''}
                ${data.empty_rhetoric > 0 ? `
                <div class="stat">
                    <span class="stat-label">Empty Rhetoric:</span>
                    <span class="stat-value rhetoric">${data.empty_rhetoric}</span>
                </div>` : ''}
            </div>
        `;
        
        container.appendChild(speakerCard);
    });
}

// Helper functions
function getScoreClass(score) {
    if (score >= 80) return 'excellent';
    if (score >= 60) return 'good';
    if (score >= 40) return 'fair';
    if (score >= 20) return 'poor';
    return 'very-poor';
}

function getScoreColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#fbbf24';
    if (score >= 40) return '#f59e0b';
    if (score >= 20) return '#f87171';
    return '#ef4444';
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// UI state management
function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function updateProgress(progress, message) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    
    if (progressBar) progressBar.style.width = `${progress}%`;
    if (progressText) progressText.textContent = message;
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        errorDiv.remove();
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
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `factcheck_${currentJobId}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            throw new Error('Export failed');
        }
    } catch (error) {
        showError('Error exporting results: ' + error.message);
    }
}

// Start new analysis
function startNewAnalysis() {
    currentJobId = null;
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('text-input').value = '';
    document.getElementById('youtube-url').value = '';
}
