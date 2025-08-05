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

// Override the displayResults function to show ALL information including speaker context
window.displayResults = function(results) {
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
    
    // Count verdicts properly
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

// Enhanced verdict helpers
window.getVerdictClass = function(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.class : 'unverified';
};

window.getVerdictIcon = function(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.icon : 'fa-question-circle';
};

window.formatVerdict = function(verdict) {
    const v = verdict.toLowerCase().replace(' ', '_');
    const mapping = VERDICT_MAPPINGS[v];
    return mapping ? mapping.label : verdict.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
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
`;
document.head.appendChild(style);
