// Congressional Features JavaScript

// State management for congressional data
let currentMemberId = null;
let currentMemberData = null;
let currentSpeeches = [];
let currentVotes = [];
let selectedSpeechIds = [];

// Initialize congressional features
function initCongressionalFeatures() {
    // Add event listeners
    document.getElementById('find-reps-btn')?.addEventListener('click', findRepresentatives);
    document.getElementById('zip-input')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') findRepresentatives();
    });
    
    // Initialize tooltips
    initTooltips();
}

// Find representatives by ZIP code
async function findRepresentatives() {
    const zipCode = document.getElementById('zip-input').value.trim();
    
    if (!zipCode) {
        showAlert('Please enter a ZIP code', 'warning');
        return;
    }
    
    if (!/^\d{5}(-\d{4})?$/.test(zipCode)) {
        showAlert('Please enter a valid ZIP code', 'warning');
        return;
    }
    
    showLoader('Finding your representatives...');
    
    try {
        const response = await fetch('/api/congress/find-reps', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ zip_code: zipCode })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRepresentatives(data);
        } else {
            showAlert(data.error || 'Failed to find representatives', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Display found representatives
function displayRepresentatives(data) {
    const container = document.getElementById('representatives-list');
    container.innerHTML = '';
    
    // Location info
    if (data.location) {
        const locationDiv = document.createElement('div');
        locationDiv.className = 'location-info';
        locationDiv.innerHTML = `
            <h3>Location: ${data.location.city}, ${data.location.state}</h3>
        `;
        container.appendChild(locationDiv);
    }
    
    // Senators section
    if (data.senators && data.senators.length > 0) {
        const senatorsSection = document.createElement('div');
        senatorsSection.className = 'senators-section';
        senatorsSection.innerHTML = '<h3><i class="fas fa-landmark"></i> Your Senators</h3>';
        
        const senatorsList = document.createElement('div');
        senatorsList.className = 'members-grid';
        
        data.senators.forEach(senator => {
            const card = createMemberCard(senator, 'senator');
            senatorsList.appendChild(card);
        });
        
        senatorsSection.appendChild(senatorsList);
        container.appendChild(senatorsSection);
    }
    
    // Representatives section
    if (data.representatives && data.representatives.length > 0) {
        const repsSection = document.createElement('div');
        repsSection.className = 'representatives-section';
        repsSection.innerHTML = '<h3><i class="fas fa-users"></i> Your Representative</h3>';
        
        if (data.representatives[0].note) {
            // Need full address
            const noteDiv = document.createElement('div');
            noteDiv.className = 'info-note';
            noteDiv.innerHTML = `
                <i class="fas fa-info-circle"></i>
                <p>${data.representatives[0].note}</p>
                <p>${data.representatives[0].reason}</p>
            `;
            repsSection.appendChild(noteDiv);
        } else {
            const repsList = document.createElement('div');
            repsList.className = 'members-grid';
            
            data.representatives.forEach(rep => {
                const card = createMemberCard(rep, 'representative');
                repsList.appendChild(card);
            });
            
            repsSection.appendChild(repsList);
        }
        
        container.appendChild(repsSection);
    }
    
    // Show the results section
    document.getElementById('representatives-results').style.display = 'block';
}

// Create member card
function createMemberCard(member, type) {
    const card = document.createElement('div');
    card.className = 'member-card';
    
    const partyClass = member.party === 'D' ? 'democrat' : member.party === 'R' ? 'republican' : 'independent';
    
    card.innerHTML = `
        <div class="member-header ${partyClass}">
            <h4>${member.name}</h4>
            <span class="party-badge">${member.party}</span>
        </div>
        <div class="member-info">
            <p><i class="fas fa-briefcase"></i> ${type === 'senator' ? 'U.S. Senator' : 'U.S. Representative'}</p>
            ${member.next_election ? `<p><i class="fas fa-calendar"></i> Next election: ${member.next_election}</p>` : ''}
            ${member.phone ? `<p><i class="fas fa-phone"></i> ${member.phone}</p>` : ''}
            ${member.website ? `<p><i class="fas fa-globe"></i> <a href="${member.website}" target="_blank">Official Website</a></p>` : ''}
        </div>
        <div class="member-actions">
            <button class="btn btn-primary" onclick="viewMemberDetails('${member.id}')">
                <i class="fas fa-user"></i> View Details
            </button>
            <button class="btn btn-secondary" onclick="viewSpeeches('${member.id}')">
                <i class="fas fa-microphone"></i> Speeches
            </button>
            <button class="btn btn-secondary" onclick="viewVotes('${member.id}')">
                <i class="fas fa-vote-yea"></i> Voting Record
            </button>
            <button class="btn btn-secondary" onclick="viewFinance('${member.name}')">
                <i class="fas fa-dollar-sign"></i> Campaign Finance
            </button>
        </div>
    `;
    
    return card;
}

// View member details
async function viewMemberDetails(memberId) {
    showLoader('Loading member details...');
    currentMemberId = memberId;
    
    try {
        const response = await fetch(`/api/congress/member/${memberId}`);
        const data = await response.json();
        
        if (data.success) {
            currentMemberData = data.member;
            displayMemberDetails(data.member);
        } else {
            showAlert(data.error || 'Failed to load member details', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Display member details
function displayMemberDetails(member) {
    const modal = createModal('member-details-modal', `${member.name} - Details`);
    
    const content = `
        <div class="member-details">
            <div class="detail-section">
                <h3>Contact Information</h3>
                <p><strong>Office:</strong> ${member.office || 'N/A'}</p>
                <p><strong>Phone:</strong> ${member.phone || 'N/A'}</p>
                <p><strong>Website:</strong> ${member.website ? `<a href="${member.website}" target="_blank">${member.website}</a>` : 'N/A'}</p>
            </div>
            
            <div class="detail-section">
                <h3>Social Media</h3>
                ${member.twitter ? `<p><i class="fab fa-twitter"></i> <a href="https://twitter.com/${member.twitter}" target="_blank">@${member.twitter}</a></p>` : ''}
                ${member.facebook ? `<p><i class="fab fa-facebook"></i> <a href="https://facebook.com/${member.facebook}" target="_blank">${member.facebook}</a></p>` : ''}
                ${member.youtube ? `<p><i class="fab fa-youtube"></i> <a href="https://youtube.com/${member.youtube}" target="_blank">${member.youtube}</a></p>` : ''}
            </div>
            
            <div class="detail-section">
                <h3>Voting Statistics</h3>
                <p><strong>Votes with Party:</strong> ${member.votes_with_party_pct || 0}%</p>
                <p><strong>Missed Votes:</strong> ${member.missed_votes_pct || 0}%</p>
            </div>
        </div>
    `;
    
    modal.querySelector('.modal-body').innerHTML = content;
    showModal(modal);
}

// View speeches
async function viewSpeeches(memberId) {
    showLoader('Loading speeches...');
    currentMemberId = memberId;
    
    try {
        const response = await fetch(`/api/congress/member/${memberId}/speeches`);
        const data = await response.json();
        
        if (data.success) {
            currentSpeeches = data.speeches;
            displaySpeeches(data.speeches);
        } else {
            showAlert(data.error || 'Failed to load speeches', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Display speeches
function displaySpeeches(speeches) {
    const modal = createModal('speeches-modal', 'Congressional Speeches', 'large');
    
    if (!speeches || speeches.length === 0) {
        modal.querySelector('.modal-body').innerHTML = '<p>No speeches found.</p>';
        showModal(modal);
        return;
    }
    
    let content = `
        <div class="speeches-toolbar">
            <button class="btn btn-primary" onclick="downloadSelectedSpeeches()">
                <i class="fas fa-download"></i> Download Selected as PDF
            </button>
            <button class="btn btn-secondary" onclick="selectAllSpeeches()">
                <i class="fas fa-check-square"></i> Select All
            </button>
        </div>
        <div class="speeches-list">
    `;
    
    speeches.forEach((speech, index) => {
        content += `
            <div class="speech-item">
                <div class="speech-header">
                    <input type="checkbox" class="speech-checkbox" value="${speech.id}" onchange="toggleSpeechSelection('${speech.id}')">
                    <h4>${speech.title || 'Untitled Speech'}</h4>
                    <span class="speech-date">${formatDate(speech.date)}</span>
                </div>
                <div class="speech-content">
                    <p class="speech-type"><i class="fas fa-tag"></i> ${speech.type || 'Floor Speech'}</p>
                    <p class="speech-summary">${speech.content ? speech.content.substring(0, 200) + '...' : 'No content available'}</p>
                    <div class="speech-actions">
                        <button class="btn btn-small btn-primary" onclick="analyzeSpeech('${speech.id}', ${index})">
                            <i class="fas fa-search"></i> Fact Check
                        </button>
                        ${speech.url ? `<a href="${speech.url}" target="_blank" class="btn btn-small btn-secondary">
                            <i class="fas fa-external-link-alt"></i> View Original
                        </a>` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    content += '</div>';
    
    modal.querySelector('.modal-body').innerHTML = content;
    showModal(modal);
}

// Toggle speech selection
function toggleSpeechSelection(speechId) {
    const index = selectedSpeechIds.indexOf(speechId);
    if (index > -1) {
        selectedSpeechIds.splice(index, 1);
    } else {
        selectedSpeechIds.push(speechId);
    }
}

// Select all speeches
function selectAllSpeeches() {
    const checkboxes = document.querySelectorAll('.speech-checkbox');
    const allChecked = selectedSpeechIds.length === currentSpeeches.length;
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
    });
    
    if (allChecked) {
        selectedSpeechIds = [];
    } else {
        selectedSpeechIds = currentSpeeches.map(s => s.id);
    }
}

// Download selected speeches
async function downloadSelectedSpeeches() {
    if (selectedSpeechIds.length === 0) {
        showAlert('Please select at least one speech', 'warning');
        return;
    }
    
    showLoader('Generating PDF...');
    
    try {
        const response = await fetch(`/api/congress/member/${currentMemberId}/speeches/download`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ speech_ids: selectedSpeechIds })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `congressional-speeches-${currentMemberId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showAlert('PDF downloaded successfully', 'success');
        } else {
            const error = await response.json();
            showAlert(error.error || 'Failed to generate PDF', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Analyze a speech
async function analyzeSpeech(speechId, speechIndex) {
    const speech = currentSpeeches[speechIndex];
    if (!speech || !speech.content) {
        showAlert('Speech content not available for analysis', 'warning');
        return;
    }
    
    showLoader('Submitting speech for fact-checking...');
    
    try {
        const response = await fetch('/api/congress/analyze-speech', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                speech_id: speechId,
                member_id: currentMemberId,
                speech_text: speech.content
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Close the speeches modal
            closeModal('speeches-modal');
            
            // Show progress and redirect to main fact-checking UI
            showAlert('Speech submitted for analysis. Redirecting...', 'success');
            
            // Store the job ID and redirect
            sessionStorage.setItem('congressionalJobId', result.job_id);
            setTimeout(() => {
                // Hide congressional section, show main analysis section
                document.getElementById('congressional-section').style.display = 'none';
                document.getElementById('input-section').style.display = 'none';
                document.getElementById('progress-section').style.display = 'block';
                
                // Start polling for this job
                currentJobId = result.job_id;
                pollJobStatus();
            }, 1500);
        } else {
            showAlert(result.error || 'Failed to submit speech', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// View voting record
async function viewVotes(memberId) {
    showLoader('Loading voting record...');
    currentMemberId = memberId;
    
    try {
        const response = await fetch(`/api/congress/member/${memberId}/votes`);
        const data = await response.json();
        
        if (data.success) {
            currentVotes = data.votes;
            displayVotingRecord(data);
        } else {
            showAlert(data.error || 'Failed to load voting record', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Display voting record
function displayVotingRecord(data) {
    const modal = createModal('votes-modal', 'Voting Record', 'large');
    
    let content = '<div class="voting-record">';
    
    // Voting analysis summary
    if (data.analysis) {
        content += `
            <div class="voting-summary">
                <h3>Voting Analysis</h3>
                <div class="stats-grid">
                    <div class="stat">
                        <span class="stat-value">${data.analysis.total_votes}</span>
                        <span class="stat-label">Total Votes</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value">${data.analysis.party_line_votes}</span>
                        <span class="stat-label">Party Line Votes</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value">${data.analysis.bipartisan_votes}</span>
                        <span class="stat-label">Bipartisan Votes</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Individual votes
    content += '<div class="votes-list">';
    
    if (!data.votes || data.votes.length === 0) {
        content += '<p>No voting record available.</p>';
    } else {
        data.votes.forEach(vote => {
            const positionClass = vote.position === 'Yes' ? 'vote-yes' : vote.position === 'No' ? 'vote-no' : 'vote-abstain';
            
            content += `
                <div class="vote-item">
                    <div class="vote-header">
                        <h4>${vote.bill_title || vote.question}</h4>
                        <span class="vote-position ${positionClass}">${vote.position}</span>
                    </div>
                    <div class="vote-details">
                        <p class="vote-date"><i class="fas fa-calendar"></i> ${formatDate(vote.date)}</p>
                        ${vote.bill_id ? `<p class="vote-bill"><i class="fas fa-file-alt"></i> ${vote.bill_id}</p>` : ''}
                        <p class="vote-result"><i class="fas fa-poll"></i> Result: ${vote.result}</p>
                    </div>
                </div>
            `;
        });
    }
    
    content += '</div></div>';
    
    modal.querySelector('.modal-body').innerHTML = content;
    showModal(modal);
}

// View campaign finance
async function viewFinance(memberName) {
    showLoader('Loading campaign finance data...');
    
    try {
        const response = await fetch(`/api/congress/member/${encodeURIComponent(memberName)}/finance`);
        const data = await response.json();
        
        if (data.success) {
            displayCampaignFinance(data);
        } else {
            showAlert(data.error || 'Failed to load campaign finance data', 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        hideLoader();
    }
}

// Display campaign finance
function displayCampaignFinance(data) {
    const modal = createModal('finance-modal', `Campaign Finance - ${data.member_name}`, 'large');
    
    const finance = data.finance;
    
    let content = '<div class="campaign-finance">';
    
    // Financial summary
    content += `
        <div class="finance-summary">
            <h3>Financial Summary</h3>
            <div class="stats-grid">
                <div class="stat">
                    <span class="stat-value">$${formatMoney(finance.total_raised)}</span>
                    <span class="stat-label">Total Raised</span>
                </div>
                <div class="stat">
                    <span class="stat-value">$${formatMoney(finance.total_spent)}</span>
                    <span class="stat-label">Total Spent</span>
                </div>
                <div class="stat">
                    <span class="stat-value">$${formatMoney(finance.cash_on_hand)}</span>
                    <span class="stat-label">Cash on Hand</span>
                </div>
                ${finance.debt ? `<div class="stat">
                    <span class="stat-value">$${formatMoney(finance.debt)}</span>
                    <span class="stat-label">Debt</span>
                </div>` : ''}
            </div>
        </div>
    `;
    
    // Contribution breakdown
    if (finance.individual_contributions || finance.pac_contributions) {
        content += `
            <div class="contribution-breakdown">
                <h3>Contribution Sources</h3>
                <div class="contribution-chart">
                    <div class="contribution-item">
                        <span class="contribution-label">Individual Contributions</span>
                        <span class="contribution-value">$${formatMoney(finance.individual_contributions || 0)}</span>
                    </div>
                    <div class="contribution-item">
                        <span class="contribution-label">PAC Contributions</span>
                        <span class="contribution-value">$${formatMoney(finance.pac_contributions || 0)}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Last updated
    if (finance.last_updated) {
        content += `<p class="finance-updated">Last updated: ${formatDate(finance.last_updated)}</p>`;
    }
    
    content += '</div>';
    
    modal.querySelector('.modal-body').innerHTML = content;
    showModal(modal);
}

// Utility functions

function showLoader(message) {
    const loader = document.getElementById('congress-loader') || createLoader();
    loader.querySelector('.loader-text').textContent = message;
    loader.style.display = 'flex';
}

function hideLoader() {
    const loader = document.getElementById('congress-loader');
    if (loader) {
        loader.style.display = 'none';
    }
}

function createLoader() {
    const loader = document.createElement('div');
    loader.id = 'congress-loader';
    loader.className = 'loader-overlay';
    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div>
            <p class="loader-text">Loading...</p>
        </div>
    `;
    document.body.appendChild(loader);
    return loader;
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'times-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(alertDiv);
        }, 300);
    }, 3000);
}

function createModal(id, title, size = 'medium') {
    const existing = document.getElementById(id);
    if (existing) {
        return existing;
    }
    
    const modal = document.createElement('div');
    modal.id = id;
    modal.className = `modal ${size}`;
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
                <button class="modal-close" onclick="closeModal('${id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body"></div>
        </div>
    `;
    
    document.body.appendChild(modal);
    return modal;
}

function showModal(modal) {
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.classList.add('show');
    }, 100);
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatMoney(amount) {
    if (!amount) return '0';
    return amount.toLocaleString('en-US');
}

function initTooltips() {
    // Initialize any tooltips if needed
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initCongressionalFeatures);
