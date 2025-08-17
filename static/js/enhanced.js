// Enhanced JavaScript for Transcript Fact Checker

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

// Function to determine alert type based on speaker context
function getSpeakerAlertType(context) {
    if (context.criminal_record) {
        return 'danger';
    } else if (context.fraud_history) {
        return 'warning';
    } else if (context.fact_check_history && context.fact_check_history.toLowerCase().includes('false')) {
        return 'warning';
    } else if (context.credibility_notes && context.credibility_notes.toLowerCase().includes('accurate')) {
        return 'success';
    } else {
        return 'info';
    }
}

// Function to generate speaker context HTML dynamically
function generateSpeakerContextHTML(context) {
    if (!context || !context.speaker) {
        return '';
    }
    
    let html = '<div class="speaker-context-section">';
    html += `<h4>About ${context.speaker}:</h4>`;
    
    // Determine the overall context type
    const alertType = getSpeakerAlertType(context);
    
    // Criminal record
    if (context.criminal_record) {
        html += `<div class="alert alert-danger">
            <strong>⚖️ Criminal Record:</strong> ${context.criminal_record}
        </div>`;
    }
    
    // Fraud history
    if (context.fraud_history) {
        html += `<div class="alert alert-warning">
            <strong>💰 Fraud History:</strong> ${context.fraud_history}
        </div>`;
    }
    
    // Fact-checking history
    if (context.fact_check_history) {
        const alertClass = context.fact_check_history.toLowerCase().includes('false') ? 'warning' : 'info';
        html += `<div class="alert alert-${alertClass}">
            <strong>📊 Fact-Check History:</strong> ${context.fact_check_history}
        </div>`;
    }
    
    // Credibility notes
    if (context.credibility_notes) {
        const alertClass = context.credibility_notes.toLowerCase().includes('accurate') ? 'success' : 'info';
        html += `<div class="alert alert-${alertClass}">
            <strong>📝 Credibility Notes:</strong> ${context.credibility_notes}
        </div>`;
    }
    
    html += '</div>';
    return html;
}

// Function to display demo mode notes
function getDemoNotes() {
    return `
        <div class="analysis-notes">
            <h4>⚠️ Demo Mode Active</h4>
            <ul>
                <li>Using simulated fact-checking for demonstration</li>
                <li>Live API integration available with valid API keys</li>
                <li>All verdicts and explanations are examples only</li>
            </ul>
        </div>
    `;
}

// Enhanced display function with all improvements
window.displayResults = function(results) {
    // First call the basic display to set up core elements
    const score = results.credibility_score || 0;
    document.getElementById('credibility-value').textContent = Math.round(score);
    document.getElementById('credibility-label').textContent = getCredibilityLabel(score);
    
    // Update credibility meter pointer
    const pointer = document.getElementById('credibility-pointer');
    const position = (score / 100) * 100;
    pointer.style.left = `calc(${position}% - 3px)`;
    
    // Update summary
    document.getElementById('analysis-summary').textContent = results.summary || 'Analysis complete.';
    
    // Display speaker info if available
    if (results.speaker) {
        const speakerDiv = document.createElement('div');
        speakerDiv.className = 'speaker-info';
        speakerDiv.innerHTML = `<strong>Speaker Identified:</strong> ${results.speaker}`;
        const summaryParent = document.getElementById('analysis-summary').parentElement;
        // Check if speaker info already exists
        const existingSpeaker = summaryParent.querySelector('.speaker-info');
        if (!existingSpeaker) {
            summaryParent.appendChild(speakerDiv);
        }
    }
    
    // Display topics if available
    if (results.topics && results.topics.length > 0) {
        const topicsDiv = document.createElement('div');
        topicsDiv.className = 'topic-info';
        topicsDiv.innerHTML = `<strong>Topics Discussed:</strong> ${results.topics.join(', ')}`;
        const summaryParent = document.getElementById('analysis-summary').parentElement;
        // Check if topics info already exists
        const existingTopics = summaryParent.querySelector('.topic-info');
        if (!existingTopics) {
            summaryParent.appendChild(topicsDiv);
        }
    }
    
    // Display speaker context if available
    if (results.speaker_context) {
        const contextHtml = generateSpeakerContextHTML(results.speaker_context);
        const summarySection = document.getElementById('analysis-summary').parentElement;
        // Check if context already exists
        const existingContext = summarySection.querySelector('.speaker-context-section');
        if (!existingContext) {
            summarySection.insertAdjacentHTML('afterbegin', contextHtml);
        }
    }
    
    // Add demo mode notes if in demo mode
    if (results.mode === 'demo') {
        const notesHtml = getDemoNotes();
        const summarySection = document.getElementById('analysis-summary').parentElement;
        // Check if notes already exist
        const existingNotes = summarySection.querySelector('.analysis-notes');
        if (!existingNotes) {
            summarySection.insertAdjacentHTML('beforeend', notesHtml);
        }
    }
    
    // Display conversational summary if available
    if (results.conversational_summary) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'conversational-summary';
        summaryDiv.innerHTML = `
            <h4>Summary</h4>
            <p>${results.conversational_summary}</p>
        `;
        const summaryParent = document.getElementById('analysis-summary').parentElement;
        // Check if conversational summary already exists
        const existingConvSummary = summaryParent.querySelector('.conversational-summary');
        if (!existingConvSummary) {
            summaryParent.appendChild(summaryDiv);
        }
    }
    
    // Update statistics with proper counts
    const totalClaims = results.fact_checks ? results.fact_checks.length : 0;
    document.getElementById('total-claims').textContent = totalClaims;
    
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
};

// Enhanced fact check display with meaningful explanations
window.displayFactChecks = function(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    factChecks.forEach((check, index) => {
        const verdict = check.verdict.toLowerCase().replace(' ', '_');
        const verdictInfo = VERDICT_MAPPINGS[verdict] || VERDICT_MAPPINGS['unverified'];
        
        const item = document.createElement('div');
        item.className = `fact-check-item ${verdictInfo.class}`;
        
        const itemId = `fact-check-${index}`;
        
        // Use full claim if available
        const claimText = check.full_context || check.claim;
        const claimSnippet = claimText.length > 100 ? 
            claimText.substring(0, 100) + '...' : claimText;
        
        // Create meaningful explanation text
        let explanationHtml = '';
        
        // For "lacks critical context", explain WHAT context is missing
        if (verdict === 'lacks_context' || verdict === 'lacks_critical_context') {
            explanationHtml = `
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
        } else if (verdict === 'deceptive') {
            explanationHtml = `
                <div class="explanation-section">
                    <h4>Why This Is Deceptive:</h4>
                    <p>${check.explanation}</p>
                </div>
            `;
        } else {
            explanationHtml = `
                <div class="explanation-section">
                    <h4>Explanation:</h4>
                    <p>${check.explanation}</p>
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
                </div>
            </div>
            <div class="fact-check-details-wrapper" id="${itemId}" style="display: none;">
                <div class="fact-check-details">
                    <div class="original-text-section">
                        <h4>Full Claim</h4>
                        <p class="original-text">"${claimText}"</p>
                    </div>
                    
                    ${explanationHtml}
                    
                    ${check.context_note ? `
                    <div class="context-resolution">
                        <h4>Context Resolution</h4>
                        <p>${check.context_note}</p>
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
};

// Toggle fact check dropdown
window.toggleFactCheck = function(itemId) {
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
};

// Enhanced verdict helpers - override basic versions
window.getVerdictClass = function(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.class : 'unverified';
};

window.getVerdictIcon = function(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.icon : 'fa-question-circle';
};

window.formatVerdict = function(verdict) {
    if (!verdict) return 'Unverified';
    
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.label : verdict.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Helper function for credibility label
window.getCredibilityLabel = function(score) {
    if (score >= 80) return 'Highly Credible';
    if (score >= 60) return 'Moderately Credible';
    if (score >= 40) return 'Low Credibility';
    return 'Very Low Credibility';
};

// Add CSS for speaker context display
const style = document.createElement('style');
style.textContent = `
.speaker-context-section {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
}

.speaker-context-section h4 {
    color: #495057;
    margin-bottom: 15px;
    font-size: 20px;
}

.alert {
    padding: 12px 20px;
    margin-bottom: 10px;
    border-radius: 4px;
}

.alert-danger {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
}

.alert-warning {
    background-color: #fff3cd;
    border: 1px solid #ffeeba;
    color: #856404;
}

.alert-info {
    background-color: #d1ecf1;
    border: 1px solid #bee5eb;
    color: #0c5460;
}

.alert-success {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
}

.conversational-summary {
    font-size: 16px;
    line-height: 1.6;
    margin: 20px 0;
}

.conversational-summary h4 {
    margin-bottom: 10px;
}

.missing-context-box {
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 12px;
    margin-top: 10px;
}

.analysis-notes {
    margin-top: 20px;
    padding: 16px;
    background-color: #fef3c7;
    border-radius: 8px;
    border-left: 4px solid #f59e0b;
}

.analysis-notes h4 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #92400e;
}

.analysis-notes ul {
    margin: 0;
    padding-left: 20px;
}

.analysis-notes li {
    color: #78350f;
    margin-bottom: 4px;
}

.speaker-info, .topic-info {
    margin-top: 12px;
    padding: 8px 12px;
    background-color: #f3f4f6;
    border-radius: 6px;
    font-size: 14px;
    color: #4b5563;
}

.speaker-info strong, .topic-info strong {
    color: #1f2937;
    margin-right: 6px;
}

/* Verdict-specific enhancements */
.fact-check-item.deceptive {
    border-color: #dc2626;
}

.fact-check-item.deceptive .fact-check-header {
    background-color: rgba(220, 38, 38, 0.05);
}

.fact-check-verdict.deceptive {
    background: #dc2626;
    color: white;
}

.fact-check-item.lacks_context {
    border-color: #06b6d4;
}

.fact-check-item.lacks_context .fact-check-header {
    background-color: rgba(6, 182, 212, 0.05);
}

.fact-check-verdict.lacks_context {
    background: #06b6d4;
    color: white;
}

/* Enhanced styling for fact check items */
.fact-check-item {
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    margin-bottom: 16px;
    transition: all 0.3s ease;
    overflow: hidden;
}

.fact-check-item:hover {
    border-color: #d1d5db;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.fact-check-header {
    padding: 16px 20px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    transition: background-color 0.2s;
}

.fact-check-header:hover {
    background-color: rgba(0, 0, 0, 0.02);
}

.fact-check-claim {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    font-weight: 500;
    color: #1f2937;
    line-height: 1.5;
}

.toggle-icon {
    color: #6b7280;
    transition: transform 0.3s ease;
}

.fact-check-details-wrapper {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
}

.fact-check-details-wrapper[style*="block"] {
    max-height: 2000px;
}

.fact-check-details {
    padding: 20px;
    background-color: #f9fafb;
    border-top: 1px solid #e5e7eb;
}

.fact-check-details h4 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #1f2937;
}

.original-text-section {
    margin-bottom: 20px;
}

.original-text {
    font-style: italic;
    color: #4b5563;
    line-height: 1.6;
}

.explanation-section,
.context-resolution,
.confidence-section,
.sources-section,
.primary-source {
    margin-top: 20px;
}

.confidence-bar {
    width: 100%;
    height: 8px;
    background-color: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
    margin: 8px 0;
}

.confidence-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #6366f1);
    transition: width 0.5s ease;
}

.confidence-text {
    font-size: 14px;
    color: #6b7280;
}

.sources-section ul {
    list-style: none;
    padding: 0;
    margin: 8px 0 0 0;
}

.sources-section li {
    padding: 6px 0;
    color: #4b5563;
    font-size: 14px;
}

.primary-source a {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #3b82f6;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s;
}

.primary-source a:hover {
    color: #2563eb;
    text-decoration: underline;
}

/* Mixed verdict styling */
.fact-check-item.mixed {
    border-color: #8b5cf6;
}

.fact-check-item.mixed .fact-check-header {
    background-color: rgba(139, 92, 246, 0.05);
}

.fact-check-verdict.mixed {
    background: #8b5cf6;
    color: white;
}

/* Unsubstantiated verdict styling */
.fact-check-item.unsubstantiated {
    border-color: #6b7280;
}

.fact-check-item.unsubstantiated .fact-check-header {
    background-color: rgba(107, 114, 128, 0.05);
}

.fact-check-verdict.unsubstantiated {
    background: #6b7280;
    color: white;
}
`;
document.head.appendChild(style);
