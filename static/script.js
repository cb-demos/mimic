// Settings management using localStorage
class Settings {
    static STORAGE_KEY = 'mimic_settings';
    
    static load() {
        try {
            const settings = localStorage.getItem(this.STORAGE_KEY);
            return settings ? JSON.parse(settings) : {};
        } catch (e) {
            console.error('Failed to load settings:', e);
            return {};
        }
    }
    
    static save(settings) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(settings));
            return true;
        } catch (e) {
            console.error('Failed to save settings:', e);
            return false;
        }
    }
    
    static get(key, defaultValue = '') {
        const settings = this.load();
        return settings[key] || defaultValue;
    }
    
    static set(key, value) {
        const settings = this.load();
        settings[key] = value;
        return this.save(settings);
    }
    
    static getAll() {
        return this.load();
    }
    
    static clear() {
        try {
            localStorage.removeItem(this.STORAGE_KEY);
            return true;
        } catch (e) {
            console.error('Failed to clear settings:', e);
            return false;
        }
    }
}

// Scenario form handling
class ScenarioForm {
    constructor() {
        this.initializeEventListeners();
        this.populateSettingsOnLoad();
    }
    
    initializeEventListeners() {
        // Toggle scenario expansion
        document.addEventListener('click', (e) => {
            if (e.target.closest('.scenario-item')) {
                const item = e.target.closest('.scenario-item');
                const form = item.querySelector('.scenario-form');
                if (form && !e.target.closest('.scenario-form')) {
                    this.toggleScenario(item, form);
                }
            }
        });
        
        // Handle form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.matches('.scenario-execute-form')) {
                e.preventDefault();
                this.handleScenarioSubmission(e.target);
            } else if (e.target.matches('.settings-form')) {
                e.preventDefault();
                this.handleSettingsSubmission(e.target);
            }
        });
        
        // Auto-populate forms when they become visible
        document.addEventListener('DOMContentLoaded', () => {
            this.populateSettingsOnLoad();
        });
    }
    
    toggleScenario(item, form) {
        // Close other scenarios
        document.querySelectorAll('.scenario-item').forEach(otherItem => {
            if (otherItem !== item) {
                otherItem.classList.remove('expanded');
                const otherForm = otherItem.querySelector('.scenario-form');
                if (otherForm) {
                    otherForm.classList.remove('expanded');
                }
            }
        });
        
        // Toggle current scenario
        item.classList.toggle('expanded');
        form.classList.toggle('expanded');
        
        // Populate form with stored settings if newly opened
        if (form.classList.contains('expanded')) {
            this.populateFormWithSettings(form);
        }
    }
    
    populateSettingsOnLoad() {
        // Populate settings form if it exists
        const settingsForm = document.querySelector('.settings-form');
        if (settingsForm) {
            const settings = Settings.getAll();
            Object.entries(settings).forEach(([key, value]) => {
                const input = settingsForm.querySelector(`[name="${key}"]`);
                if (input) {
                    input.value = value;
                }
            });
        }
        
        // Also listen for changes on settings inputs to auto-save
        const settingsInputs = document.querySelectorAll('.inline-settings input');
        settingsInputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.autoSaveSettings();
            });
        });
    }
    
    autoSaveSettings() {
        const settingsForm = document.querySelector('.settings-form');
        if (settingsForm) {
            const formData = new FormData(settingsForm);
            const settings = {};
            
            for (const [key, value] of formData.entries()) {
                if (value.trim()) {
                    settings[key] = value.trim();
                }
            }
            
            Settings.save(settings);
            // Optionally show a brief "saved" indicator
            this.showBriefMessage('Settings auto-saved', 'success');
        }
    }
    
    populateFormWithSettings(form) {
        const settings = Settings.getAll();
        
        // Map settings to common form field names
        const fieldMapping = {
            'target_org': 'target_org',
            'organization_id': 'organization_id',
            'invitee_username': 'invitee_username',
            'unify_pat': 'unify_pat'
        };
        
        Object.entries(fieldMapping).forEach(([settingKey, fieldName]) => {
            const input = form.querySelector(`[name="${fieldName}"]`);
            const value = settings[settingKey];
            if (input && value) {
                input.value = value;
            }
        });
    }
    
    async handleScenarioSubmission(form) {
        const formData = new FormData(form);
        const scenarioId = form.dataset.scenarioId;
        
        if (!scenarioId) {
            this.showMessage('Error: No scenario ID found', 'error');
            return;
        }
        
        // Build request payload
        const payload = {
            organization_id: formData.get('organization_id'),
            unify_pat: formData.get('unify_pat'),
            invitee_username: formData.get('invitee_username') || null,
            parameters: {}
        };
        
        // Add scenario parameters
        for (const [key, value] of formData.entries()) {
            if (!['organization_id', 'unify_pat', 'invitee_username'].includes(key) && value) {
                payload.parameters[key] = value;
            }
        }
        
        try {
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Executing...';
            
            this.showMessage('Starting scenario execution...', 'info');
            
            const response = await fetch(`/instantiate/${scenarioId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showExecutionResults(result);
                this.showMessage('Scenario executed successfully!', 'success');
            } else {
                this.showMessage(`Error: ${result.detail || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Execution error:', error);
            this.showMessage(`Network error: ${error.message}`, 'error');
        } finally {
            const submitBtn = form.querySelector('[type="submit"]');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Execute Scenario';
        }
    }
    
    handleSettingsSubmission(form) {
        const formData = new FormData(form);
        const settings = {};
        
        for (const [key, value] of formData.entries()) {
            if (value.trim()) {
                settings[key] = value.trim();
            }
        }
        
        if (Settings.save(settings)) {
            this.showMessage('Settings saved successfully!', 'success');
        } else {
            this.showMessage('Failed to save settings', 'error');
        }
    }
    
    showMessage(message, type = 'info') {
        // Remove existing messages
        document.querySelectorAll('.status-message').forEach(msg => msg.remove());
        
        const messageEl = document.createElement('div');
        messageEl.className = `status-message ${type}`;
        messageEl.textContent = message;
        
        // Insert before the scenario grid (after the h1 and description)
        const scenarioGrid = document.querySelector('.scenario-grid');
        if (scenarioGrid) {
            scenarioGrid.insertAdjacentElement('beforebegin', messageEl);
        } else {
            // Fallback to beginning of content if scenario grid not found
            const target = document.querySelector('.sheet-content') || document.body;
            target.insertBefore(messageEl, target.firstChild);
        }
        
        // Auto-remove after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => messageEl.remove(), 5000);
        }
    }
    
    showBriefMessage(message, type = 'info') {
        // Remove existing brief messages
        document.querySelectorAll('.brief-message').forEach(msg => msg.remove());
        
        const messageEl = document.createElement('div');
        messageEl.className = `status-message ${type} brief-message`;
        messageEl.textContent = message;
        messageEl.style.fontSize = '14px';
        messageEl.style.padding = '0.5rem 1rem';
        
        // Insert after settings card
        const settingsCard = document.querySelector('.settings-card');
        if (settingsCard) {
            settingsCard.insertAdjacentElement('afterend', messageEl);
            // Auto-remove after 2 seconds
            setTimeout(() => messageEl.remove(), 2000);
        }
    }
    
    showExecutionResults(result) {
        const resultsContainer = document.querySelector('.execution-results') || this.createResultsContainer();
        
        let html = '<h4>Execution Results</h4>';
        
        if (result.summary) {
            const summary = result.summary;
            html += '<div class="results-section">';
            
            if (summary.components && summary.components.length > 0) {
                html += '<p><strong>Components created:</strong></p>';
                html += '<ul>' + summary.components.map(c => `<li>${c}</li>`).join('') + '</ul>';
            }
            
            if (summary.environments && summary.environments.length > 0) {
                html += '<p><strong>Environments created:</strong></p>';
                html += '<ul>' + summary.environments.map(e => `<li>${e}</li>`).join('') + '</ul>';
            }
            
            if (summary.applications && summary.applications.length > 0) {
                html += '<p><strong>Applications created:</strong></p>';
                html += '<ul>' + summary.applications.map(a => `<li>${a}</li>`).join('') + '</ul>';
            }
            
            if (summary.flags && summary.flags.length > 0) {
                html += '<p><strong>Feature flags created:</strong></p>';
                html += '<ul>' + summary.flags.map(f => `<li>${f}</li>`).join('') + '</ul>';
            }
            
            if (summary.repositories && summary.repositories.length > 0) {
                html += '<p><strong>GitHub repositories:</strong></p>';
                html += '<ul>' + summary.repositories.map(repo => 
                    `<li><a href="${repo.html_url}" target="_blank" rel="noopener">${repo.full_name}</a>${repo.existed ? ' (existing)' : ''}</li>`
                ).join('') + '</ul>';
            }
            
            html += '</div>';
        }
        
        resultsContainer.innerHTML = html;
        resultsContainer.style.display = 'block';
    }
    
    createResultsContainer() {
        const container = document.createElement('div');
        container.className = 'execution-results';
        container.style.display = 'none';
        
        const target = document.querySelector('.sheet-content');
        if (target) {
            target.appendChild(container);
        }
        
        return container;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ScenarioForm();
});