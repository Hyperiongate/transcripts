// truthlens-display.js - Consolidated Display and UI Methods

class TruthLensDisplay {
    constructor(app) {
        this.app = app;
        this.charts = {};
    }

    showResults(data) {
        const resultsSection = document.getElementById('resultsSection');
        if (!resultsSection) return;
        if (!data || !data.analysis) return;

        resultsSection.style.display = 'block';
        resultsSection.classList.add('active');
        
        this.displayTrustScore(data.analysis, data);
        this.displayKeyFindings(data);
        this.displayArticleInfo(data.article);
        this.displayServiceAccordion(data);
        
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    displayTrustScore(analysis, fullData) {
        const score = analysis.trust_score || 0;
        const level = analysis.trust_level || 'Unknown';
        
        // Animate score
        this.animateScore('trustScoreNumber', score);
        
        // Update level indicator
        const indicatorEl = document.getElementById('trustLevelIndicator');
        const iconEl = document.getElementById('trustLevelIcon');
        const textEl = document.getElementById('trustLevelText');
        
        if (indicatorEl && iconEl && textEl) {
            const config = this.getTrustLevelConfig(score);
            indicatorEl.className = 'trust-level-indicator ' + config.class;
            iconEl.className = 'fas ' + config.icon + ' trust-level-icon';
            iconEl.style.color = config.color;
            textEl.textContent = config.text;
            textEl.style.color = config.color;
        }
        
        // Create gauge
        this.createTrustGauge('trustGauge', score);
        
        // Update summary - FIXED to include source name
        const summaryEl = document.getElementById('trustSummary');
        if (summaryEl) {
            summaryEl.innerHTML = this.getTrustSummary(score, level, fullData);
        }
        
        // Display breakdown
        this.displayTrustBreakdown(fullData.detailed_analysis || {});
    }

    getTrustLevelConfig(score) {
        if (score >= 80) return { class: 'level-very-high', icon: 'fa-check-circle', color: '#10b981', text: 'Very High Credibility' };
        if (score >= 60) return { class: 'level-high', icon: 'fa-check', color: '#3b82f6', text: 'High Credibility' };
        if (score >= 40) return { class: 'level-moderate', icon: 'fa-exclamation-circle', color: '#f59e0b', text: 'Moderate Credibility' };
        if (score >= 20) return { class: 'level-low', icon: 'fa-times-circle', color: '#ef4444', text: 'Low Credibility' };
        return { class: 'level-very-low', icon: 'fa-times-circle', color: '#dc2626', text: 'Very Low Credibility' };
    }

    getTrustSummary(score, level, data) {
        const metadata = this.app.state.currentMetadata || {};
        const servicesUsed = metadata.services_used || [];
        
        // The source name is successfully found in the source_credibility service
        // So let's get it from there directly
        let sourceName = 'Unknown Source';
        
        // Get it directly from where we know it exists - source_credibility service
        if (data.detailed_analysis && data.detailed_analysis.source_credibility && data.detailed_analysis.source_credibility.source_name) {
            sourceName = data.detailed_analysis.source_credibility.source_name;
        }
        
        let summary = '<strong>Source:</strong> ' + sourceName + '<br><br>';
        
        if (score >= 80) {
            summary += '<strong style="color: #10b981;">High Credibility:</strong> This article demonstrates exceptional journalistic standards. ';
            summary += 'Our analysis of ' + servicesUsed.length + ' key factors indicates this is a highly reliable source.';
        } else if (score >= 60) {
            summary += '<strong style="color: #3b82f6;">Moderate Credibility:</strong> Reasonable journalistic standards with some concerns. ';
            summary += 'While generally reputable, some issues warrant careful consideration.';
        } else if (score >= 40) {
            summary += '<strong style="color: #f59e0b;">Low Credibility:</strong> Significant credibility issues identified. ';
            summary += 'Multiple red flags detected. Verify information through additional sources.';
        } else {
            summary += '<strong style="color: #ef4444;">Very Low Credibility:</strong> Fails to meet basic journalistic standards. ';
            summary += 'Major concerns identified. Exercise extreme caution.';
        }
        
        return summary;
    }

    displayKeyFindings(data) {
        const container = document.getElementById('keyFindings');
        if (!container) return;

        const findings = (data.analysis && data.analysis.key_findings) || this.generateFindings(data);
        
        if (findings.length > 0) {
            let html = '<div class="key-findings-header">Key Findings</div>';
            html += '<div class="findings-grid">';
            findings.forEach(function(finding) {
                html += window.truthLensApp.display.renderFinding(finding);
            });
            html += '</div>';
            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="info-box">' +
                '<div class="info-box-title">' +
                '<i class="fas fa-info-circle"></i>' +
                'Analysis Complete' +
                '</div>' +
                '<div class="info-box-content">' +
                'Review the detailed findings below to understand the credibility assessment.' +
                '</div>' +
                '</div>';
        }
    }

    renderFinding(finding) {
        const config = {
            positive: { icon: 'fa-check-circle', color: '#10b981' },
            negative: { icon: 'fa-times-circle', color: '#ef4444' },
            warning: { icon: 'fa-exclamation-circle', color: '#f59e0b' }
        };
        
        const type = finding.type || 'warning';
        const typeConfig = config[type] || config.warning;
        const icon = typeConfig.icon;
        const color = typeConfig.color;
        
        return '<div class="finding-item finding-' + type + '">' +
            '<div class="finding-icon" style="color: ' + color + ';">' +
            '<i class="fas ' + icon + '"></i>' +
            '</div>' +
            '<div class="finding-content">' +
            '<strong class="finding-title">' + (finding.title || finding.finding) + '</strong>' +
            '<p class="finding-explanation">' + (finding.explanation || finding.text || '') + '</p>' +
            '</div>' +
            '</div>';
    }

    generateFindings(data) {
        const findings = [];
        const analysis = data.detailed_analysis || {};
        
        // Source credibility
        if (analysis.source_credibility) {
            const sourceScore = analysis.source_credibility.credibility_score || analysis.source_credibility.score || 0;
            const sourceName = analysis.source_credibility.source_name || 'the source';
            
            if (sourceScore >= 80) {
                findings.push({
                    type: 'positive',
                    title: 'Highly Reputable Source',
                    explanation: sourceName + ' is a well-established news outlet with strong editorial standards.'
                });
            } else if (sourceScore < 50) {
                findings.push({
                    type: 'negative',
                    title: 'Source Credibility Concerns',
                    explanation: sourceName + ' has limited credibility indicators or history of misinformation.'
                });
            }
        }

        // Author credibility - FIXED to check credibility_score
        if (analysis.author_analyzer) {
            const authorScore = analysis.author_analyzer.author_score || 
                               analysis.author_analyzer.credibility_score || 
                               analysis.author_analyzer.score || 0;
            const authorName = analysis.author_analyzer.author_name || 'The author';
            
            if (authorScore >= 70) {
                findings.push({
                    type: 'positive',
                    title: 'Credible Author',
                    explanation: authorName + ' has verified credentials and journalistic experience.'
                });
            } else if (authorScore < 40 || !analysis.author_analyzer.author_name) {
                findings.push({
                    type: 'warning',
                    title: 'Limited Author Information',
                    explanation: 'Unable to verify author credentials, which may affect reliability.'
                });
            }
        }

        // Bias detection
        if (analysis.bias_detector) {
            const biasScore = analysis.bias_detector.bias_score || analysis.bias_detector.score || 0;
            
            if (biasScore > 70) {
                findings.push({
                    type: 'negative',
                    title: 'High Bias Detected',
                    explanation: 'Significant bias indicators (' + biasScore + '% bias score) affect objectivity.'
                });
            } else if (biasScore < 30) {
                findings.push({
                    type: 'positive',
                    title: 'Balanced Reporting',
                    explanation: 'Article maintains objectivity with neutral language and balanced perspectives.'
                });
            }
        }

        // Fact checking
        if (analysis.fact_checker && analysis.fact_checker.fact_checks && analysis.fact_checker.fact_checks.length > 0) {
            const checks = analysis.fact_checker.fact_checks;
            const verified = checks.filter(function(c) {
                return ['True', 'Verified', 'true', 'verified'].indexOf(c.verdict) !== -1;
            }).length;
            const percentage = Math.round((verified / checks.length) * 100);
            
            if (percentage >= 80) {
                findings.push({
                    type: 'positive',
                    title: 'Facts Verified',
                    explanation: percentage + '% of claims (' + verified + '/' + checks.length + ') have been verified.'
                });
            } else if (percentage < 50) {
                findings.push({
                    type: 'negative',
                    title: 'Unverified Claims',
                    explanation: 'Only ' + percentage + '% of claims could be verified. Fact-check independently.'
                });
            }
        }

        // Sort findings: negative first, then warning, then positive
        return findings.sort(function(a, b) {
            const order = { negative: 0, warning: 1, positive: 2 };
            return order[a.type] - order[b.type];
        }).slice(0, 4); // Limit to 4 key findings
    }

    displayTrustBreakdown(detailedAnalysis) {
        const container = document.getElementById('trustBreakdown');
        if (!container) return;

        const components = [
            {
                name: 'Source Reputation',
                score: this.app.utils.extractScore(detailedAnalysis.source_credibility, ['credibility_score', 'score'], 50),
                icon: 'fa-building',
                color: '#6366f1',
                meaning: this.getSourceMeaning(detailedAnalysis.source_credibility)
            },
            {
                name: 'Author Credibility',
                // FIXED: Include credibility_score in the fields to check
                score: this.app.utils.extractScore(detailedAnalysis.author_analyzer, ['author_score', 'credibility_score', 'score'], 50),
                icon: 'fa-user',
                color: '#10b981',
                meaning: this.getAuthorMeaning(detailedAnalysis.author_analyzer)
            },
            {
                name: 'Transparency',
                score: this.app.utils.extractScore(detailedAnalysis.transparency_analyzer, ['transparency_score', 'score'], 50),
                icon: 'fa-eye',
                color: '#f59e0b',
                meaning: this.getTransparencyMeaning(detailedAnalysis.transparency_analyzer)
            },
            {
                name: 'Objectivity',
                score: detailedAnalysis.bias_detector ? 
                    (100 - (detailedAnalysis.bias_detector.bias_score || detailedAnalysis.bias_detector.score || 0)) : 50,
                icon: 'fa-balance-scale',
                color: '#ef4444',
                meaning: this.getObjectivityMeaning(detailedAnalysis.bias_detector)
            }
        ];

        let html = '';
        components.forEach(function(comp) {
            html += window.truthLensApp.display.renderBreakdownItem(comp);
        });
        container.innerHTML = html;

        // Animate the progress bars after rendering
        setTimeout(function() {
            components.forEach(function(comp, index) {
                const fills = container.querySelectorAll('.breakdown-fill');
                if (fills[index]) {
                    fills[index].style.width = comp.score + '%';
                }
            });
        }, 100);
    }

    renderBreakdownItem(comp) {
        const scoreColor = this.app.utils.getScoreColor(comp.score);
        const statusClass = comp.score >= 80 ? 'breakdown-positive' : 
                           comp.score >= 60 ? 'breakdown-neutral' : 
                           comp.score >= 40 ? 'breakdown-warning' : 'breakdown-negative';
        
        return '<div class="breakdown-item ' + statusClass + '">' +
            '<div class="breakdown-header">' +
            '<div class="breakdown-label">' +
            '<div class="breakdown-icon" style="background: ' + comp.color + '20;">' +
            '<i class="fas ' + comp.icon + '" style="color: ' + comp.color + ';"></i>' +
            '</div>' +
            comp.name +
            '</div>' +
            '<div class="breakdown-value" style="color: ' + scoreColor + ';">' + comp.score + '%</div>' +
            '</div>' +
            '<div class="breakdown-explanation">' + comp.meaning + '</div>' +
            '<div class="breakdown-bar">' +
            '<div class="breakdown-fill" style="background: ' + scoreColor + '; width: 0%;"></div>' +
            '</div>' +
            '</div>';
    }

    getSourceMeaning(data) {
        if (!data) return 'Source credibility could not be determined.';
        const score = data.credibility_score || data.score || 0;
        
        if (score >= 80) return 'Highly credible news source with established journalistic standards.';
        if (score >= 60) return 'Reasonably credible but may lack some transparency.';
        if (score >= 40) return 'Limited credibility indicators. Verify information independently.';
        return 'Lacks basic credibility. Exercise extreme caution.';
    }

    getAuthorMeaning(data) {
        if (!data || !data.author_name) return 'Without author information, credibility cannot be fully assessed.';
        // FIXED: Check credibility_score as well
        const score = data.author_score || data.credibility_score || data.score || 0;
        
        if (score >= 80) return 'Verified journalist with strong credentials.';
        if (score >= 60) return 'Some journalism experience but limited verification.';
        if (score >= 40) return 'Limited information raises credibility concerns.';
        return 'Lack of author transparency is a significant concern.';
    }

    getTransparencyMeaning(data) {
        if (!data) return 'Transparency level could not be determined.';
        const score = data.transparency_score || data.score || 0;
        
        if (score >= 80) return 'Excellent transparency with clear sourcing and disclosures.';
        if (score >= 60) return 'Good transparency but missing some key elements.';
        if (score >= 40) return 'Some transparency issues that warrant attention.';
        return 'Limited transparency raises questions about hidden agendas.';
    }

    getObjectivityMeaning(data) {
        if (!data) return 'Bias level could not be determined.';
        const biasScore = data.bias_score || data.score || 0;
        
        if (biasScore < 30) return 'Maintains objectivity and presents balanced perspectives.';
        if (biasScore < 60) return 'Some bias within acceptable journalistic standards.';
        return 'Significant bias detected. Seek alternative perspectives.';
    }

    displayArticleInfo(article) {
        if (!article) return;
        
        const titleEl = document.getElementById('articleTitle');
        const metaEl = document.getElementById('articleMeta');
        
        if (titleEl) {
            titleEl.textContent = article.title || 'Untitled Article';
        }
        
        if (metaEl) {
            const metaItems = [];
            
            if (article.author) {
                metaItems.push('<div class="meta-item"><i class="fas fa-user"></i><span>' + article.author + '</span></div>');
            }
            
            // FIXED: Better source display
            const source = article.source || article.domain || 'Unknown Source';
            metaItems.push('<div class="meta-item"><i class="fas fa-globe"></i><span>' + source + '</span></div>');
            
            if (article.publish_date) {
                metaItems.push('<div class="meta-item"><i class="fas fa-calendar"></i><span>' + this.app.utils.formatDate(article.publish_date) + '</span></div>');
            }
            
            if (article.word_count) {
                metaItems.push('<div class="meta-item"><i class="fas fa-file-alt"></i><span>' + article.word_count + ' words</span></div>');
            }
            
            metaEl.innerHTML = metaItems.join('');
        }
    }

    displayServiceAccordion(data) {
        const container = document.getElementById('servicesAccordion');
        if (!container) return;
        
        const servicesData = data.detailed_analysis || {};
        
        let html = '';
        CONFIG.services.forEach(function(service, index) {
            const serviceData = servicesData[service.id] || {};
            html += window.truthLensApp.display.createServiceAccordionItem(service, serviceData, index);
        });
        
        container.innerHTML = html;
    }

    createServiceAccordionItem(service, serviceData, index) {
        const hasData = serviceData && Object.keys(serviceData).length > 0;
        const score = this.getServiceScore(service.id, serviceData);
        const scoreColor = score !== null ? this.app.utils.getScoreColor(score) : '#9ca3af';
        const preview = this.getServicePreview(service.id, serviceData);
        
        return '<div class="service-accordion-item" id="service-' + service.id + '">' +
            '<div class="service-accordion-header" onclick="window.truthLensApp.toggleAccordion(\'' + service.id + '\')">' +
            '<div class="service-header-content">' +
            '<div class="service-icon-wrapper">' +
            '<i class="fas ' + service.icon + '"></i>' +
            '</div>' +
            '<div class="service-info">' +
            '<h3 class="service-name">' + service.name + '</h3>' +
            '<p class="service-description">' + service.description + '</p>' +
            (hasData ? '<div class="service-preview">' + preview + '</div>' : 
                '<div class="service-preview"><span class="preview-value" style="color: #9ca3af;">Analysis not available</span></div>') +
            '</div>' +
            '</div>' +
            (service.isPro && !CONFIG.isPro ? 
                '<span class="pro-lock-badge"><i class="fas fa-lock"></i> PRO</span>' : 
                '<i class="fas fa-chevron-down service-expand-icon"></i>') +
            (hasData ? '<div class="data-state-indicator"></div>' : '<div class="data-state-indicator no-data"></div>') +
            '</div>' +
            '<div class="service-accordion-content">' +
            '<div class="service-content-inner">' +
            (hasData && this.app.services ? this.app.services.renderService(service.id, serviceData) : 
                '<div class="empty-state">' +
                '<i class="fas fa-inbox"></i>' +
                '<div class="empty-state-text">No data available</div>' +
                '<div class="empty-state-subtext">This analysis could not be performed</div>' +
                '</div>') +
            '</div>' +
            '</div>' +
            '</div>';
    }

    getServiceScore(serviceId, data) {
        if (!data || Object.keys(data).length === 0) return null;
        
        switch (serviceId) {
            case 'source_credibility':
                return data.credibility_score || data.score || null;
            case 'author_analyzer':
                // FIXED: Check credibility_score which is what the backend returns
                return data.author_score || data.credibility_score || data.score || null;
            case 'bias_detector':
                const biasScore = data.bias_score || data.score;
                return biasScore !== undefined ? (100 - biasScore) : null;
            case 'fact_checker':
                if (data.fact_checks && Array.isArray(data.fact_checks) && data.fact_checks.length > 0) {
                    const verified = data.fact_checks.filter(function(c) {
                        return ['True', 'Verified', 'true', 'verified'].indexOf(c.verdict) !== -1;
                    }).length;
                    return Math.round((verified / data.fact_checks.length) * 100);
                }
                return data.accuracy_score || data.score || null;
            case 'transparency_analyzer':
                return data.transparency_score || data.score || null;
            case 'manipulation_detector':
                const manipScore = data.manipulation_score || data.score;
                return manipScore !== undefined ? (100 - manipScore) : null;
            case 'content_analyzer':
                return data.quality_score || data.score || null;
            case 'plagiarism_detector':
                if (data.originality_score !== undefined) return data.originality_score;
                if (data.plagiarism_score !== undefined) return (100 - data.plagiarism_score);
                return null;
            default:
                return null;
        }
    }

    getServicePreview(serviceId, data) {
        if (!data || Object.keys(data).length === 0) {
            return '<span class="preview-value" style="color: #9ca3af;">Not Available</span>';
        }
        
        const previews = {
            source_credibility: function() {
                const score = data.credibility_score || data.score || 0;
                const level = data.level || window.truthLensApp.services.getCredibilityLevel(score);
                return '<span class="preview-item"><span class="preview-label">Score:</span> <span class="preview-value">' + 
                       score + '/100</span></span> <span class="preview-item"><span class="preview-label">Level:</span> <span class="preview-value">' + 
                       level + '</span></span>';
            },
            author_analyzer: function() {
                const name = data.author_name || 'Unknown';
                // FIXED: Check credibility_score as well
                const score = data.author_score || data.credibility_score || data.score || 0;
                return '<span class="preview-item"><span class="preview-label">Author:</span> <span class="preview-value">' + 
                       name + '</span></span> <span class="preview-item"><span class="preview-label">Score:</span> <span class="preview-value">' + 
                       score + '/100</span></span>';
            },
            bias_detector: function() {
                const bias = data.bias_score || data.score || 0;
                const level = data.bias_level || window.truthLensApp.services.getBiasLevel(bias);
                return '<span class="preview-item"><span class="preview-label">Bias:</span> <span class="preview-value">' + 
                       bias + '%</span></span> <span class="preview-item"><span class="preview-label">Level:</span> <span class="preview-value">' + 
                       level + '</span></span>';
            },
            fact_checker: function() {
                const total = (data.fact_checks && data.fact_checks.length) || 0;
                const verified = (data.fact_checks && data.fact_checks.filter(function(c) {
                    return ['True', 'Verified', 'true', 'verified'].indexOf(c.verdict) !== -1;
                }).length) || 0;
                return '<span class="preview-item"><span class="preview-label">Claims:</span> <span class="preview-value">' + 
                       total + '</span></span> <span class="preview-item"><span class="preview-label">Verified:</span> <span class="preview-value">' + 
                       verified + '</span></span>';
            },
            transparency_analyzer: function() {
                const score = data.transparency_score || data.score || 0;
                const level = data.transparency_level || window.truthLensApp.services.getTransparencyLevel(score);
                return '<span class="preview-item"><span class="preview-label">Score:</span> <span class="preview-value">' + 
                       score + '%</span></span> <span class="preview-item"><span class="preview-label">Level:</span> <span class="preview-value">' + 
                       level + '</span></span>';
            },
            manipulation_detector: function() {
                const level = data.manipulation_level || data.level || 'Unknown';
                const tactics = (data.tactics_found || data.tactics || []).length;
                return '<span class="preview-item"><span class="preview-label">Risk:</span> <span class="preview-value">' + 
                       level + '</span></span> <span class="preview-item"><span class="preview-label">Tactics:</span> <span class="preview-value">' + 
                       tactics + '</span></span>';
            },
            content_analyzer: function() {
                const quality = data.quality_score || data.score || 0;
                const readability = data.readability && data.readability.level ? data.readability.level : 'Unknown';
                return '<span class="preview-item"><span class="preview-label">Quality:</span> <span class="preview-value">' + 
                       quality + '%</span></span> <span class="preview-item"><span class="preview-label">Readability:</span> <span class="preview-value">' + 
                       readability + '</span></span>';
            },
            plagiarism_detector: function() {
                const originality = data.originality_score || (100 - (data.plagiarism_score || 0)) || 0;
                const sources = (data.matched_sources || []).length;
                return '<span class="preview-item"><span class="preview-label">Original:</span> <span class="preview-value">' + 
                       originality + '%</span></span> <span class="preview-item"><span class="preview-label">Matches:</span> <span class="preview-value">' + 
                       sources + '</span></span>';
            }
        };
        
        const previewFunc = previews[serviceId];
        return previewFunc ? previewFunc() : 'Analysis complete';
    }

    animateScore(elementId, targetScore) {
        const el = document.getElementById(elementId);
        if (!el) return;
        
        // Ensure score is within bounds
        targetScore = Math.min(100, Math.max(0, targetScore));
        
        let current = 0;
        const increment = targetScore / 30;
        const timer = setInterval(function() {
            current += increment;
            if (current >= targetScore) {
                current = targetScore;
                clearInterval(timer);
            }
            el.textContent = Math.round(current);
        }, 30);
    }

    createTrustGauge(elementId, score) {
        const canvas = document.getElementById(elementId);
        if (!canvas || !window.Chart) return;
        
        // Ensure score is within bounds
        score = Math.min(100, Math.max(0, score));
        
        // Destroy existing chart
        if (this.charts[elementId]) {
            this.charts[elementId].destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
        const color = this.app.utils.getScoreColor(score);
        
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, color + '99');
        
        this.charts[elementId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [score, 100 - score],
                    backgroundColor: [gradient, '#e5e7eb'],
                    borderWidth: 0
                }]
            },
            options: {
                rotation: -90,
                circumference: 180,
                responsive: true,
                maintainAspectRatio: false,
                cutout: '80%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            }
        });
    }
}
