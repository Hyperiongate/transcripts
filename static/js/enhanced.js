// Enhanced JavaScript for Transcript Fact Checker

// Enhanced verdict handling
const VERDICT_MAPPINGS = {
    'true': { class: 'true', icon: 'fa-check-circle', label: 'True' },
    'mostly_true': { class: 'true', icon: 'fa-check-circle', label: 'Mostly True' },
    'mixed': { class: 'mixed', icon: 'fa-adjust', label: 'Mixed' },
    'misleading': { class: 'misleading', icon: 'fa-exclamation-triangle', label: 'Misleading' },
    'lacks_context': { class: 'lacks_context', icon: 'fa-info-circle', label: 'Lacks Context' },
    'unsubstantiated': { class: 'unsubstantiated', icon: 'fa-question-circle', label: 'Unsubstantiated' },
    'mostly_false': { class: 'false', icon: 'fa-times-circle', label: 'Mostly False' },
    'false': { class: 'false', icon: 'fa-times-circle', label: 'False' },
    'unverified': { class: 'unverified', icon: 'fa-question-circle', label: 'Unverified' }
};

// Override the existing displayFactChecks function
window.displayFactChecks = function(factChecks) {
    const container = document.getElementById('fact-check-list');
    container.innerHTML = '';
    
    factChecks.forEach((check, index) => {
        const verdict = check.verdict.toLowerCase().replace(' ', '_');
        const verdictInfo = VERDICT_MAPPINGS[verdict] || VERDICT_MAPPINGS['unverified'];
        
        const item = document.createElement('div');
        item.className = `fact-check-item ${verdictInfo.class}`;
        
        // Create unique ID for this fact check
        const itemId = `fact-check-${index}`;
        
        // Use snippet for header, full context in details
        const claimSnippet = check.claim.length > 100 ? 
            check.claim.substring(0, 100) + '...' : check.claim;
        
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
                    ${check.full_context && check.full_context !== check.claim ? `
                    <div class="original-text-section">
                        <h4>Full Context</h4>
                        <p class="original-text">"${check.full_context}"</p>
                    </div>
                    ` : `
                    <div class="original-text-section">
                        <h4>Full Claim</h4>
                        <p class="original-text">"${check.claim}"</p>
                    </div>
                    `}
                    
                    <div class="explanation-section">
                        <h4>Explanation</h4>
                        <p>${check.explanation}</p>
                    </div>
                    
                    ${check.confidence ? `
                    <div class="confidence-section">
                        <h4>Confidence Level</h4>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${check.confidence}%"></div>
                        </div>
                        <span class="confidence-text">${check.confidence}% confident</span>
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
};

// Enhanced verdict counting
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
    
    // Display conversational summary if available
    let summaryHtml = '';
    if (results.conversational_summary) {
        summaryHtml = `<p>${results.conversational_summary}</p>`;
    } else {
        summaryHtml = `<p>${results.summary}</p>`;
    }
    
    // Add speaker history if available
    if (results.speaker && results.speaker_history) {
        summaryHtml += `
            <div class="speaker-history">
                <h4>About ${results.speaker}:</h4>
                <p>We've analyzed content from this speaker ${results.speaker_history.total_analyses} times. 
                Their average credibility score is ${results.speaker_history.average_credibility.toFixed(0)}%.</p>
            </div>
        `;
    }
    
    document.getElementById('analysis-summary').innerHTML = summaryHtml;
    
    // Display analysis notes if present
    if (results.analysis_notes && results.analysis_notes.length > 0) {
        const notesHtml = results.analysis_notes.map(note => `<li>${note}</li>`).join('');
        document.getElementById('analysis-summary').innerHTML += `
            <div class="analysis-notes">
                <h4>Important Notes:</h4>
                <ul>${notesHtml}</ul>
            </div>
        `;
    }
    
    // Update statistics
    document.getElementById('total-claims').textContent = results.checked_claims;
    
    // Enhanced verdict counting
    let verifiedCount = 0;
    let falseCount = 0;
    let unverifiedCount = 0;
    
    results.fact_checks.forEach(check => {
        const verdict = check.verdict.toLowerCase().replace(' ', '_');
        
        // Count as verified
        if (verdict === 'true' || verdict === 'mostly_true') {
            verifiedCount++;
        }
        // Count as false
        else if (verdict === 'false' || verdict === 'mostly_false') {
            falseCount++;
        }
        // Everything else is unverified (including mixed, misleading, lacks_context)
        else {
            unverifiedCount++;
        }
    });
    
    document.getElementById('verified-claims').textContent = verifiedCount;
    document.getElementById('false-claims').textContent = falseCount;
    document.getElementById('unverified-claims').textContent = unverifiedCount;
    
    // Display fact checks with enhanced dropdowns
    displayFactChecks(results.fact_checks);
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
