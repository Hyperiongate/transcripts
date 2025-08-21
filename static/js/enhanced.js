// Enhanced verdict mappings
const VERDICT_MAPPINGS = {
    'true': { class: 'true', icon: 'fa-check-circle', label: 'True' },
    'mostly_true': { class: 'true', icon: 'fa-check-circle', label: 'Mostly True' },
    'nearly_true': { class: 'true', icon: 'fa-check-circle', label: 'Nearly True' },
    'exaggeration': { class: 'unverified', icon: 'fa-exclamation-circle', label: 'Exaggeration' },
    'misleading': { class: 'false', icon: 'fa-exclamation-triangle', label: 'Misleading' },
    'mostly_false': { class: 'false', icon: 'fa-times-circle', label: 'Mostly False' },
    'false': { class: 'false', icon: 'fa-times-circle', label: 'False' },
    'intentionally_deceptive': { class: 'false', icon: 'fa-exclamation-triangle', label: 'Intentionally Deceptive' },
    'needs_context': { class: 'unverified', icon: 'fa-question-circle', label: 'Needs Context' },
    'opinion': { class: 'unverified', icon: 'fa-comment', label: 'Opinion' },
    'unverified': { class: 'unverified', icon: 'fa-question-circle', label: 'Unverified' }
};

// Enhanced helper functions
window.getVerdictClass = function(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    return VERDICT_MAPPINGS[v]?.class || 'unverified';
};

window.getVerdictIcon = function(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    return VERDICT_MAPPINGS[v]?.icon || 'fa-question-circle';
};

window.formatVerdict = function(verdict) {
    const v = (verdict || 'unverified').toLowerCase().replace(' ', '_');
    return VERDICT_MAPPINGS[v]?.label || verdict.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};
