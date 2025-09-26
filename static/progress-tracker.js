/**
 * Progress Tracker Web Component
 * Real-time scenario execution progress with Server-Sent Events
 */

class ProgressTracker extends HTMLElement {
    constructor() {
        super();
        this.sessionId = null;
        this.eventSource = null;
        this.isVisible = false;
        this.progressData = {
            currentStep: null,
            percentage: 0,
            steps: [],
            logs: [],
            isComplete: false,
            hasFailed: false
        };

        // Step definitions with descriptions
        this.stepDefinitions = {
            'initialization': {
                label: 'Initializing',
                description: 'Preparing scenario execution'
            },
            'repository_creation': {
                label: 'Creating Repositories',
                description: 'Setting up GitHub repositories from templates'
            },
            'component_creation': {
                label: 'Creating Components',
                description: 'Mapping repositories to CloudBees components'
            },
            'flag_creation': {
                label: 'Planning Feature Flags',
                description: 'Defining feature flag configurations'
            },
            'environment_creation': {
                label: 'Setting up Environments',
                description: 'Creating CloudBees environments with variables'
            },
            'application_creation': {
                label: 'Creating Applications',
                description: 'Linking components and environments'
            },
            'environment_fm_token_update': {
                label: 'Configuring SDK Keys',
                description: 'Adding feature management tokens'
            },
            'flag_configuration': {
                label: 'Configuring Feature Flags',
                description: 'Setting up flags across environments'
            }
        };
    }

    connectedCallback() {
        this.render();
        this.attachEventListeners();
    }

    disconnectedCallback() {
        this.cleanup();
    }

    render() {
        this.innerHTML = `
            <div class="progress-modal" id="progress-modal" style="display: none;">
                <div class="progress-card">
                    <div class="progress-header">
                        <h3>Executing Scenario</h3>
                        <div class="progress-percentage">
                            <span id="progress-text">0%</span>
                        </div>
                    </div>

                    <div class="progress-bar-container">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>

                    <div class="progress-steps" id="progress-steps">
                        <!-- Steps will be populated dynamically -->
                    </div>

                    <div class="progress-logs">
                        <div class="logs-header">
                            <h4>Execution Log</h4>
                            <button class="logs-toggle" id="logs-toggle" aria-expanded="false">
                                Show Details
                            </button>
                        </div>
                        <div class="logs-content" id="logs-content" style="display: none;">
                            <div class="logs-list" id="logs-list">
                                <!-- Logs will be populated here -->
                            </div>
                        </div>
                    </div>

                    <div class="progress-actions" id="progress-actions" style="display: none;">
                        <button class="btn primary" onclick="this.closest('progress-tracker').hide()">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    attachEventListeners() {
        // Toggle logs visibility
        const logsToggle = this.querySelector('#logs-toggle');
        const logsContent = this.querySelector('#logs-content');

        logsToggle.addEventListener('click', () => {
            const isExpanded = logsToggle.getAttribute('aria-expanded') === 'true';
            logsToggle.setAttribute('aria-expanded', !isExpanded);
            logsToggle.textContent = isExpanded ? 'Show Details' : 'Hide Details';
            logsContent.style.display = isExpanded ? 'none' : 'block';
        });

        // Close modal on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });

        // Close modal on backdrop click
        const modal = this.querySelector('#progress-modal');
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hide();
            }
        });
    }

    show(sessionId) {
        this.sessionId = sessionId;
        this.isVisible = true;
        this.resetProgress();

        const modal = this.querySelector('#progress-modal');
        modal.style.display = 'flex';

        // Start listening for progress events
        this.startProgressStream();
    }

    hide() {
        this.isVisible = false;
        const modal = this.querySelector('#progress-modal');
        modal.style.display = 'none';

        this.cleanup();
    }

    resetProgress() {
        this.progressData = {
            currentStep: null,
            percentage: 0,
            steps: [],
            logs: [],
            isComplete: false,
            hasFailed: false
        };

        // Reset UI
        this.updateProgressBar(0);
        this.querySelector('#progress-steps').innerHTML = '';
        this.querySelector('#logs-list').innerHTML = '';
        this.querySelector('#progress-actions').style.display = 'none';
    }

    startProgressStream() {
        if (!this.sessionId) {
            console.error('No session ID provided for progress stream');
            return;
        }

        // Close existing connection
        this.cleanup();

        console.log(`Starting progress stream for session: ${this.sessionId}`);
        this.addLog(`Connecting to progress stream...`, 'info');

        try {
            this.eventSource = new EventSource(`/api/scenario/${this.sessionId}/progress`);

            this.eventSource.onopen = (event) => {
                console.log('Progress stream connected');
                this.addLog('Connected to progress stream', 'success');
            };

            this.eventSource.onmessage = (event) => {
                try {
                    console.log('Received progress event:', event.data);
                    const progressEvent = JSON.parse(event.data);
                    this.handleProgressEvent(progressEvent);
                } catch (e) {
                    console.error('Failed to parse progress event:', e, event.data);
                    this.addLog(`Parse error: ${e.message}`, 'error');
                }
            };

            this.eventSource.onerror = (error) => {
                console.error('Progress stream error:', error);
                if (this.eventSource.readyState === EventSource.CLOSED) {
                    this.addLog('Connection closed', 'error');
                } else {
                    this.addLog('Connection error - retrying...', 'error');
                }
            };

        } catch (e) {
            console.error('Failed to start progress stream:', e);
            this.addLog(`Failed to connect: ${e.message}`, 'error');
        }
    }

    handleProgressEvent(event) {
        switch (event.event_type) {
            case 'step_started':
                this.startStep(event.step, event.message, event.percentage);
                break;
            case 'step_completed':
                this.completeStep(event.step, event.message, event.percentage);
                break;
            case 'step_failed':
                this.failStep(event.step, event.message);
                break;
            case 'log_message':
                this.addLog(event.message, 'info');
                break;
            case 'scenario_completed':
                this.completeScenario(event.message, event.details);
                break;
            case 'scenario_failed':
                this.failScenario(event.message, event.details);
                break;
        }
    }

    startStep(stepKey, message, percentage) {
        this.progressData.currentStep = stepKey;
        if (percentage !== undefined) {
            this.updateProgressBar(percentage);
        }

        this.updateStepDisplay();
        this.addLog(message, 'info');
    }

    completeStep(stepKey, message, percentage) {
        if (percentage !== undefined) {
            this.updateProgressBar(percentage);
        }

        // Mark step as completed
        if (!this.progressData.steps.includes(stepKey)) {
            this.progressData.steps.push(stepKey);
        }

        this.updateStepDisplay();
        this.addLog(message, 'success');
    }

    failStep(stepKey, message) {
        this.progressData.hasFailed = true;
        this.addLog(message, 'error');
        this.showActions();
    }

    completeScenario(message, details) {
        this.progressData.isComplete = true;
        this.updateProgressBar(100);
        this.addLog(message, 'success');
        this.showActions();
        this.cleanup();
    }

    failScenario(message, details) {
        this.progressData.hasFailed = true;
        this.addLog(message, 'error');
        this.showActions();
        this.cleanup();
    }

    updateProgressBar(percentage) {
        this.progressData.percentage = percentage;

        const progressFill = this.querySelector('#progress-fill');
        const progressText = this.querySelector('#progress-text');

        progressFill.style.width = `${percentage}%`;
        progressText.textContent = `${percentage}%`;
    }

    updateStepDisplay() {
        const stepsContainer = this.querySelector('#progress-steps');
        const steps = Object.keys(this.stepDefinitions);

        stepsContainer.innerHTML = steps.map(stepKey => {
            const step = this.stepDefinitions[stepKey];
            const isCompleted = this.progressData.steps.includes(stepKey);
            const isCurrent = this.progressData.currentStep === stepKey;
            const isFailed = this.progressData.hasFailed && isCurrent;

            let statusClass = '';
            let statusIcon = '';

            if (isFailed) {
                statusClass = 'failed';
                statusIcon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
            } else if (isCompleted) {
                statusClass = 'completed';
                statusIcon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20,6 9,17 4,12"/></svg>';
            } else if (isCurrent) {
                statusClass = 'active';
                statusIcon = '<svg class="btn-spinner" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>';
            }

            return `
                <div class="progress-step ${statusClass}">
                    <div class="step-icon">${statusIcon}</div>
                    <div class="step-content">
                        <div class="step-title">${step.label}</div>
                        <div class="step-description">${step.description}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    addLog(message, type = 'info') {
        this.progressData.logs.push({
            message,
            type,
            timestamp: new Date().toLocaleTimeString()
        });

        const logsList = this.querySelector('#logs-list');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="log-time">${new Date().toLocaleTimeString()}</span>
            <span class="log-message">${message}</span>
        `;

        logsList.appendChild(logEntry);
        logsList.scrollTop = logsList.scrollHeight;
    }

    showActions() {
        this.querySelector('#progress-actions').style.display = 'flex';
    }

    cleanup() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

// Register the custom element
customElements.define('progress-tracker', ProgressTracker);