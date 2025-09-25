/**
 * Authentication Web Component
 * Provides 1Password-like authentication experience
 */
class AuthComponent extends HTMLElement {
    constructor() {
        super();

        this.state = {
            isLoading: false,
            error: null,
            showOptionalFields: false
        };

        this.render();
        this.setupEventListeners();
    }

    render() {
        this.innerHTML = `
            <div class="auth-overlay">
                <div class="auth-container">
                    <div class="auth-header">
                        <div class="auth-logo">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                                <line x1="9" y1="9" x2="9.01" y2="9"/>
                                <line x1="15" y1="9" x2="15.01" y2="9"/>
                            </svg>
                        </div>
                        <h1>Welcome to CloudBees Scenario Manager</h1>
                        <p>Sign in to get started with demo scenarios</p>
                    </div>

                    <form class="auth-form" id="auth-form">
                        <div class="form-group">
                            <label for="auth-email">Company Email *</label>
                            <input
                                type="email"
                                id="auth-email"
                                name="email"
                                required
                                placeholder="you@cloudbees.com"
                                autocomplete="email"
                            >
                        </div>

                        <div class="form-group">
                            <label for="auth-unify-pat">CloudBees Unify PAT *</label>
                            <input
                                type="password"
                                id="auth-unify-pat"
                                name="unify_pat"
                                required
                                placeholder="Enter your CloudBees Personal Access Token"
                                autocomplete="current-password"
                            >
                            <div class="form-help">
                                Your personal access token for CloudBees Platform API access. Keep this secure.
                            </div>
                        </div>

                        <div class="optional-fields" style="display: none;">
                            <div class="form-group">
                                <label for="auth-github-pat">GitHub PAT</label>
                                <input
                                    type="password"
                                    id="auth-github-pat"
                                    name="github_pat"
                                    placeholder="GitHub Personal Access Token (optional)"
                                    autocomplete="off"
                                >
                                <div class="form-help">
                                    Optional: For private GitHub organizations or enhanced features
                                </div>
                            </div>
                        </div>

                        <div class="form-actions">
                            <button type="submit" class="btn primary" id="auth-submit">
                                <span class="btn-text">Sign In</span>
                                <span class="btn-spinner" style="display: none;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M21 12a9 9 0 11-6.219-8.56"/>
                                    </svg>
                                </span>
                            </button>

                            <button type="button" class="btn secondary" id="toggle-optional">
                                Show Optional Fields
                            </button>
                        </div>

                        <div class="auth-error" id="auth-error" style="display: none;"></div>
                    </form>

                    <div class="auth-footer">
                        <p>Your credentials are encrypted and stored securely</p>
                    </div>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        const form = this.querySelector('#auth-form');
        const toggleButton = this.querySelector('#toggle-optional');
        const optionalFields = this.querySelector('.optional-fields');

        // Handle form submission
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        // Toggle optional fields
        toggleButton.addEventListener('click', () => {
            this.state.showOptionalFields = !this.state.showOptionalFields;

            if (this.state.showOptionalFields) {
                optionalFields.style.display = 'block';
                toggleButton.textContent = 'Hide Optional Fields';
            } else {
                optionalFields.style.display = 'none';
                toggleButton.textContent = 'Show Optional Fields';
            }
        });

        // Clear error on input
        form.addEventListener('input', () => {
            this.clearError();
        });
    }

    async handleSubmit() {
        const form = this.querySelector('#auth-form');
        const formData = new FormData(form);

        // Validate required fields
        const email = formData.get('email')?.trim();
        const unifyPat = formData.get('unify_pat')?.trim();

        if (!email || !unifyPat) {
            this.showError('Please fill in all required fields');
            return;
        }

        // Validate email format and domain
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            this.showError('Please enter a valid email address');
            return;
        }

        // Validate CloudBees domain
        if (!email.toLowerCase().endsWith('@cloudbees.com')) {
            this.showError('Only CloudBees email addresses are allowed');
            return;
        }

        this.setLoading(true);
        this.clearError();

        try {
            const response = await fetch('/api/auth/verify-tokens', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    unify_pat: unifyPat,
                    github_pat: formData.get('github_pat')?.trim() || null
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Authentication failed');
            }

            const userData = await response.json();

            // Store auth data in localStorage
            localStorage.setItem('mimic_user_data', JSON.stringify({
                email: userData.email,
                has_github_pat: userData.has_github_pat,
                authenticated: true
            }));

            // Hide auth component and trigger app initialization
            this.style.display = 'none';

            // Dispatch custom event to notify app that user is authenticated
            window.dispatchEvent(new CustomEvent('user-authenticated', {
                detail: userData
            }));

        } catch (error) {
            this.showError(error.message);
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(loading) {
        this.state.isLoading = loading;

        const submitButton = this.querySelector('#auth-submit');
        const btnText = submitButton.querySelector('.btn-text');
        const btnSpinner = submitButton.querySelector('.btn-spinner');

        if (loading) {
            submitButton.disabled = true;
            btnText.style.display = 'none';
            btnSpinner.style.display = 'inline-block';
        } else {
            submitButton.disabled = false;
            btnText.style.display = 'inline-block';
            btnSpinner.style.display = 'none';
        }
    }

    showError(message) {
        this.state.error = message;
        const errorDiv = this.querySelector('#auth-error');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    clearError() {
        this.state.error = null;
        const errorDiv = this.querySelector('#auth-error');
        errorDiv.style.display = 'none';
    }

    // Check if user is already authenticated
    static isAuthenticated() {
        try {
            const userData = localStorage.getItem('mimic_user_data');
            if (!userData) return false;

            const parsed = JSON.parse(userData);
            return parsed.authenticated === true && parsed.email;
        } catch (e) {
            return false;
        }
    }

    // Get current user data
    static getUserData() {
        try {
            const userData = localStorage.getItem('mimic_user_data');
            return userData ? JSON.parse(userData) : null;
        } catch (e) {
            return null;
        }
    }

    // Clear authentication
    static logout() {
        localStorage.removeItem('mimic_user_data');

        // Reload page to show auth screen
        window.location.reload();
    }
}

// Register the web component
customElements.define('auth-component', AuthComponent);

// Export for use in other scripts
window.AuthComponent = AuthComponent;