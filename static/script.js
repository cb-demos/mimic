// Organization management using localStorage
class Organizations {
    static STORAGE_KEY = 'mimic_organizations';
    static SELECTED_KEY = 'mimic_selected_org';
    
    static load() {
        try {
            const orgs = localStorage.getItem(this.STORAGE_KEY);
            return orgs ? JSON.parse(orgs) : [];
        } catch (e) {
            console.error('Failed to load organizations:', e);
            return [];
        }
    }
    
    static save(organizations) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(organizations));
            return true;
        } catch (e) {
            console.error('Failed to save organizations:', e);
            return false;
        }
    }
    
    static getSelected() {
        try {
            const selectedId = localStorage.getItem(this.SELECTED_KEY);
            const organizations = this.load();
            return organizations.find(org => org.id === selectedId) || null;
        } catch (e) {
            console.error('Failed to get selected organization:', e);
            return null;
        }
    }
    
    static setSelected(orgId) {
        try {
            localStorage.setItem(this.SELECTED_KEY, orgId);
            return true;
        } catch (e) {
            console.error('Failed to set selected organization:', e);
            return false;
        }
    }
    
    static add(organization) {
        const organizations = this.load();
        const existing = organizations.findIndex(org => org.id === organization.id);
        
        if (existing >= 0) {
            // Update existing
            organizations[existing] = organization;
        } else {
            // Add new
            organizations.push(organization);
        }
        
        return this.save(organizations);
    }
    
    static remove(orgId) {
        const organizations = this.load();
        const filtered = organizations.filter(org => org.id !== orgId);
        
        // If we're removing the selected org, clear selection
        const selected = this.getSelected();
        if (selected && selected.id === orgId) {
            localStorage.removeItem(this.SELECTED_KEY);
        }
        
        return this.save(filtered);
    }
    
    static clear() {
        try {
            localStorage.removeItem(this.STORAGE_KEY);
            localStorage.removeItem(this.SELECTED_KEY);
            return true;
        } catch (e) {
            console.error('Failed to clear organizations:', e);
            return false;
        }
    }
    
    static async fetchDetails(orgId, unifyPat) {
        try {
            const response = await fetch('/api/organizations/details', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    organization_id: orgId,
                    unify_pat: unifyPat
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to fetch organization details');
            }
            
            return await response.json();
        } catch (error) {
            throw new Error(`Failed to fetch organization details: ${error.message}`);
        }
    }
}

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

// Organization management UI
class OrganizationManager {
    static init() {
        this.populateDropdowns();
        this.initializeEventListeners();
    }
    
    static populateDropdowns() {
        const organizations = Organizations.load();
        const selected = Organizations.getSelected();
        
        // Populate main settings dropdown
        const settingsDropdown = document.getElementById('organization_selector');
        if (settingsDropdown) {
            this.populateDropdown(settingsDropdown, organizations, selected);
        }
        
        // Populate scenario form dropdowns
        document.querySelectorAll('.scenario-org-dropdown').forEach(dropdown => {
            this.populateDropdown(dropdown, organizations, selected);
        });
    }
    
    static populateDropdown(dropdown, organizations, selected) {
        // Clear existing options except the first one
        while (dropdown.children.length > 1) {
            dropdown.removeChild(dropdown.lastChild);
        }
        
        // Add organization options
        organizations.forEach(org => {
            const option = document.createElement('option');
            option.value = org.id;
            
            // Format as "displayName (truncated-uuid)"
            const truncatedUuid = org.id.substring(0, 4) + '...';
            option.textContent = `${org.displayName} (${truncatedUuid})`;
            
            if (selected && selected.id === org.id) {
                option.selected = true;
            }
            
            dropdown.appendChild(option);
        });
    }
    
    static initializeEventListeners() {
        // Handle organization selection
        document.addEventListener('change', (e) => {
            if (e.target.matches('.organization-dropdown')) {
                const orgId = e.target.value;
                if (orgId) {
                    Organizations.setSelected(orgId);
                    // Update all dropdowns to reflect selection
                    this.populateDropdowns();
                }
            }
        });
    }
    
    static showAddForm() {
        const inputGroup = document.getElementById('add_org_input_group');
        const selectGroup = document.getElementById('org_select_group');
        
        inputGroup.style.display = 'flex';
        selectGroup.style.display = 'none';
        document.getElementById('new_org_id').focus();
    }
    
    static hideAddForm() {
        const inputGroup = document.getElementById('add_org_input_group');
        const selectGroup = document.getElementById('org_select_group');
        
        inputGroup.style.display = 'none';
        selectGroup.style.display = 'flex';
        document.getElementById('new_org_id').value = '';
    }
    
    static async addOrganization() {
        const orgIdInput = document.getElementById('new_org_id');
        const orgId = orgIdInput.value.trim();
        
        if (!orgId) {
            alert('Please enter an organization ID');
            return;
        }
        
        // Validate UUID format
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(orgId)) {
            alert('Please enter a valid UUID format');
            return;
        }
        
        try {
            // Get PAT from settings
            const unifyPat = Settings.get('unify_pat');
            if (!unifyPat) {
                alert('Please set your CloudBees Unify Personal Access Token first');
                return;
            }
            
            // Show loading state
            const addBtn = document.querySelector('.input-group-btn.add-btn');
            const originalText = addBtn.textContent;
            addBtn.disabled = true;
            addBtn.textContent = '...';
            
            // Fetch organization details
            const orgDetails = await Organizations.fetchDetails(orgId, unifyPat);
            
            // Add to local storage
            Organizations.add(orgDetails);
            
            // Set as selected
            Organizations.setSelected(orgDetails.id);
            
            // Update UI
            this.populateDropdowns();
            this.hideAddForm();
            
            // Show success message
            ScenarioForm.prototype.showBriefMessage(`Added organization: ${orgDetails.displayName}`, 'success');
            
        } catch (error) {
            console.error('Failed to add organization:', error);
            alert(`Failed to add organization: ${error.message}`);
        } finally {
            // Reset button state
            const addBtn = document.querySelector('.input-group-btn.add-btn');
            addBtn.disabled = false;
            addBtn.textContent = '+';
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
        
        // Also listen for changes on settings inputs to auto-save (except org-related ones)
        const settingsInputs = document.querySelectorAll('.inline-settings input:not(#new_org_id)');
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
        }
    }
    
    populateFormWithSettings(form) {
        const settings = Settings.getAll();
        const selectedOrg = Organizations.getSelected();
        
        // Map settings to common form field names
        const fieldMapping = {
            'target_org': 'target_org',
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
        
        // Set organization dropdown to selected org
        const orgDropdown = form.querySelector('[name="organization_id"]');
        if (orgDropdown && selectedOrg) {
            orgDropdown.value = selectedOrg.id;
        }
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
    OrganizationManager.init();
    new ScenarioForm();
});