class DropdownSelector extends HTMLElement {
    constructor() {
        super();
        this.storageKey = this.getAttribute('storage-key') || 'dropdown_items';
        this.selectedKey = this.getAttribute('selected-key') || 'selected_item';
        this.placeholder = this.getAttribute('placeholder') || 'Select or add item...';
        this.inputPlaceholder = this.getAttribute('input-placeholder') || 'Enter value...';
        this.fetchEndpoint = this.getAttribute('fetch-endpoint') || null;
        this.displayField = this.getAttribute('display-field') || 'displayName';
        this.valueField = this.getAttribute('value-field') || 'id';
        this.truncateLength = parseInt(this.getAttribute('truncate-length')) || 4;
        this.requiresPat = this.getAttribute('requires-pat') === 'true';
        
        this.items = [];
        this.selectedItem = null;
        
        this.render();
        this.loadData();
        this.setupEventListeners();
    }
    
    render() {
        this.innerHTML = `
            <div class="dropdown-selector">
                <div class="input-group" id="select-group-${this.storageKey}">
                    <select class="dropdown-select">
                        <option value="">${this.placeholder}</option>
                    </select>
                    <button type="button" class="input-group-btn add-trigger-btn" title="Add new item">+</button>
                </div>
                <div class="input-group" id="add-group-${this.storageKey}" style="display: none;">
                    <input type="text" placeholder="${this.inputPlaceholder}" class="add-input">
                    <button type="button" class="input-group-btn add-btn" title="Add item">+</button>
                    <button type="button" class="input-group-btn cancel-btn" title="Cancel">×</button>
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
        const selectGroup = this.querySelector(`#select-group-${this.storageKey}`);
        const addGroup = this.querySelector(`#add-group-${this.storageKey}`);
        const dropdown = this.querySelector('.dropdown-select');
        const addTrigger = this.querySelector('.add-trigger-btn');
        const addBtn = this.querySelector('.add-btn');
        const cancelBtn = this.querySelector('.cancel-btn');
        const addInput = this.querySelector('.add-input');
        
        // Handle selection changes
        dropdown.addEventListener('change', (e) => {
            const value = e.target.value;
            if (value) {
                this.setSelected(value);
                this.dispatchEvent(new CustomEvent('item-selected', { 
                    detail: { value, item: this.getSelectedItem() }
                }));
            }
        });
        
        // Show add form
        addTrigger.addEventListener('click', () => {
            selectGroup.style.display = 'none';
            addGroup.style.display = 'flex';
            addInput.focus();
        });
        
        // Hide add form
        cancelBtn.addEventListener('click', () => {
            addGroup.style.display = 'none';
            selectGroup.style.display = 'flex';
            addInput.value = '';
        });
        
        // Add new item
        addBtn.addEventListener('click', () => this.addItem());
        addInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addItem();
            }
        });
    }
    
    loadData() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            this.items = stored ? JSON.parse(stored) : [];
            
            const selectedId = localStorage.getItem(this.selectedKey);
            this.selectedItem = this.items.find(item => item[this.valueField] === selectedId) || null;
            
            this.populateDropdown();
        } catch (e) {
            console.error('Failed to load dropdown data:', e);
            this.items = [];
            this.selectedItem = null;
        }
    }
    
    saveData() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.items));
            return true;
        } catch (e) {
            console.error('Failed to save dropdown data:', e);
            return false;
        }
    }
    
    setSelected(value) {
        try {
            localStorage.setItem(this.selectedKey, value);
            this.selectedItem = this.items.find(item => item[this.valueField] === value) || null;
            this.populateDropdown();
            return true;
        } catch (e) {
            console.error('Failed to set selected item:', e);
            return false;
        }
    }
    
    getSelectedItem() {
        return this.selectedItem;
    }
    
    getSelectedValue() {
        return this.selectedItem ? this.selectedItem[this.valueField] : null;
    }
    
    populateDropdown() {
        const dropdown = this.querySelector('.dropdown-select');
        
        // Clear existing options except placeholder
        while (dropdown.children.length > 1) {
            dropdown.removeChild(dropdown.lastChild);
        }
        
        // Add items
        this.items.forEach(item => {
            const option = document.createElement('option');
            option.value = item[this.valueField];
            
            // Format display text with truncated ID if applicable
            let displayText = item[this.displayField];
            if (item[this.valueField] !== displayText && this.truncateLength > 0) {
                const truncated = item[this.valueField].substring(0, this.truncateLength) + '...';
                displayText += ` (${truncated})`;
            }
            option.textContent = displayText;
            
            if (this.selectedItem && this.selectedItem[this.valueField] === item[this.valueField]) {
                option.selected = true;
            }
            
            dropdown.appendChild(option);
        });
    }
    
    async addItem() {
        const addInput = this.querySelector('.add-input');
        const addBtn = this.querySelector('.add-btn');
        const cancelBtn = this.querySelector('.cancel-btn');
        const value = addInput.value.trim();
        
        if (!value) {
            alert('Please enter a value');
            return;
        }
        
        try {
            // Show loading state
            addBtn.disabled = true;
            addBtn.textContent = '...';
            
            let item;
            
            if (this.fetchEndpoint) {
                // Fetch from API
                if (this.requiresPat) {
                    const unifyPat = this.getPatFromSettings();
                    if (!unifyPat) {
                        alert('Please set your CloudBees Unify Personal Access Token first');
                        return;
                    }
                    item = await this.fetchItemDetails(value, unifyPat);
                } else {
                    item = await this.fetchItemDetails(value);
                }
            } else {
                // Simple localStorage item
                item = {
                    [this.valueField]: value,
                    [this.displayField]: value
                };
            }
            
            // Add to items
            const existingIndex = this.items.findIndex(i => i[this.valueField] === item[this.valueField]);
            if (existingIndex >= 0) {
                this.items[existingIndex] = item;
            } else {
                this.items.push(item);
            }
            
            // Save and update UI
            this.saveData();
            this.setSelected(item[this.valueField]);
            this.hideAddForm();
            
            // Dispatch event
            this.dispatchEvent(new CustomEvent('item-added', { 
                detail: { item }
            }));
            
        } catch (error) {
            console.error('Failed to add item:', error);
            alert(`Failed to add item: ${error.message}`);
        } finally {
            addBtn.disabled = false;
            addBtn.textContent = '+';
        }
    }
    
    async fetchItemDetails(value, pat = null) {
        const response = await fetch(this.fetchEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                [this.valueField]: value,
                ...(pat && { unify_pat: pat })
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to fetch item details');
        }
        
        return await response.json();
    }
    
    getPatFromSettings() {
        try {
            const settings = localStorage.getItem('mimic_settings');
            const parsed = settings ? JSON.parse(settings) : {};
            return parsed.unify_pat || null;
        } catch (e) {
            return null;
        }
    }
    
    hideAddForm() {
        const selectGroup = this.querySelector(`#select-group-${this.storageKey}`);
        const addGroup = this.querySelector(`#add-group-${this.storageKey}`);
        const addInput = this.querySelector('.add-input');
        
        addGroup.style.display = 'none';
        selectGroup.style.display = 'flex';
        addInput.value = '';
    }
    
    // Public API methods
    refresh() {
        this.loadData();
    }
    
    clear() {
        localStorage.removeItem(this.storageKey);
        localStorage.removeItem(this.selectedKey);
        this.items = [];
        this.selectedItem = null;
        this.populateDropdown();
    }
}

// Register the custom element
customElements.define('dropdown-selector', DropdownSelector);