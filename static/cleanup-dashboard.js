/**
 * Cleanup Dashboard Web Component
 * Manages user's demo resource sessions with cleanup capabilities
 */
class CleanupDashboard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    this.state = {
      sessions: [],
      loading: false,
      error: null,
      cleanupInProgress: new Set(),
    };

    this.refreshData = this.refreshData.bind(this);
    this.handleCleanup = this.handleCleanup.bind(this);
    this._eventListenersSetup = false;
  }

  connectedCallback() {
    this.render();

    // Only auto-load data if this tab is currently active
    const cleanupTab = document.querySelector('tab-navigation');
    if (cleanupTab && cleanupTab.getActiveTab && cleanupTab.getActiveTab() === 'cleanup') {
      this.refreshData();
    }

    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(this.refreshData, 30000);

    // Listen for tab changes to refresh data when tab becomes active
    document.addEventListener('tab-change', (event) => {
      if (event.detail.activeTab === 'cleanup') {
        // Only refresh if we don't have data yet
        if (this.state.sessions.length === 0 && !this.state.error) {
          // Small delay to ensure DOM is ready
          setTimeout(() => this.refreshData(), 100);
        }
      }
    });
  }

  disconnectedCallback() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  static get observedAttributes() {
    return ["user-email"];
  }

  get userEmail() {
    // First try to get from attribute
    const fromAttr = this.getAttribute("user-email");
    if (fromAttr) {
      return fromAttr;
    }

    // Fallback to localStorage
    try {
      const userData = localStorage.getItem("mimic_user_data");
      if (userData) {
        const parsed = JSON.parse(userData);
        return parsed.email;
      }
    } catch (e) {
      console.error("Failed to get user email from localStorage:", e);
    }

    return null;
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
        }

        .dashboard-container {
          width: 100%;
        }

        .dashboard-header {
          margin-bottom: 2rem;
        }

        .dashboard-title {
          font-size: 1.875rem;
          font-weight: 700;
          color: #1f2937;
          margin-bottom: 0.5rem;
        }

        .dashboard-subtitle {
          color: #6b7280;
          font-size: 1.125rem;
        }

        .skeleton-container {
          padding: 1rem 0;
        }

        .skeleton-header {
          margin-bottom: 2rem;
        }

        .skeleton-line {
          background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
          background-size: 200% 100%;
          animation: skeleton-loading 1.5s infinite;
          border-radius: 4px;
          height: 1rem;
          margin-bottom: 0.5rem;
        }

        .skeleton-title {
          width: 60%;
          height: 2rem;
        }

        .skeleton-subtitle {
          width: 40%;
          height: 1.25rem;
        }

        .skeleton-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1rem;
          margin-bottom: 2rem;
        }

        .skeleton-card {
          padding: 1rem;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
        }

        .skeleton-stat-number {
          width: 50%;
          height: 1.5rem;
        }

        .skeleton-stat-label {
          width: 70%;
        }

        .skeleton-list-item {
          padding: 1rem;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          margin-bottom: 0.5rem;
        }

        .skeleton-session-name {
          width: 40%;
          height: 1.25rem;
        }

        .skeleton-session-details {
          width: 60%;
        }

        @keyframes skeleton-loading {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }

        .error-state {
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 0.5rem;
          padding: 1rem;
          color: #dc2626;
          margin-bottom: 1rem;
        }

        .empty-state {
          text-align: center;
          padding: 3rem;
          color: #6b7280;
        }

        .empty-state-icon {
          width: 4rem;
          height: 4rem;
          margin: 0 auto 1rem;
          opacity: 0.3;
        }

        .sessions-grid {
          display: grid;
          gap: 1.5rem;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        }

        .session-card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 0.75rem;
          padding: 1.5rem;
          box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
          transition: all 0.2s ease;
        }

        .session-card:hover {
          border-color: #d1d5db;
          box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }

        .session-header {
          margin-bottom: 1rem;
        }

        .session-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 0.25rem;
        }

        .session-scenario {
          color: #6b7280;
          font-size: 0.875rem;
          text-transform: uppercase;
          font-weight: 500;
        }

        .session-meta {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-bottom: 1rem;
          font-size: 0.875rem;
          color: #6b7280;
        }

        .session-created {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .session-resources {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }


        .session-actions {
          display: flex;
          gap: 0.75rem;
          margin-top: 1rem;
        }

        .btn {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          border: 1px solid transparent;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          text-decoration: none;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-primary {
          background: #dc2626;
          color: white;
          border-color: #dc2626;
        }

        .btn-primary:hover:not(:disabled) {
          background: #b91c1c;
          border-color: #b91c1c;
        }

        .btn-secondary {
          background: white;
          color: #374151;
          border-color: #d1d5db;
        }

        .btn-secondary:hover:not(:disabled) {
          background: #f9fafb;
          border-color: #9ca3af;
        }

        .btn-spinner {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }


        .status-message {
          padding: 1rem;
          border-radius: 0.5rem;
          margin-bottom: 1rem;
        }

        .status-success {
          background: #f0fdf4;
          border: 1px solid #bbf7d0;
          color: #166534;
        }

        .status-error {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
        }
      </style>

      <div class="dashboard-container">
        <div class="dashboard-header">
          <h1 class="dashboard-title">My Demo Resources</h1>
          <p class="dashboard-subtitle">Manage and clean up your CloudBees demo scenarios</p>
        </div>

        <div id="status-messages"></div>

        <div id="dashboard-content">
          ${this.renderContent()}
        </div>
      </div>
    `;

    this.setupEventListeners();
  }

  renderContent() {
    if (this.state.loading) {
      return `
        <div class="skeleton-container">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
            <div class="skeleton-line skeleton-subtitle"></div>
          </div>

          <div class="skeleton-stats">
            <div class="skeleton-card">
              <div class="skeleton-line skeleton-stat-number"></div>
              <div class="skeleton-line skeleton-stat-label"></div>
            </div>
            <div class="skeleton-card">
              <div class="skeleton-line skeleton-stat-number"></div>
              <div class="skeleton-line skeleton-stat-label"></div>
            </div>
            <div class="skeleton-card">
              <div class="skeleton-line skeleton-stat-number"></div>
              <div class="skeleton-line skeleton-stat-label"></div>
            </div>
          </div>

          <div class="skeleton-list">
            <div class="skeleton-list-item">
              <div class="skeleton-line skeleton-session-name"></div>
              <div class="skeleton-line skeleton-session-details"></div>
            </div>
          </div>
        </div>
      `;
    }

    if (this.state.error) {
      return `
        <div class="error-state">
          <strong>Error loading sessions:</strong> ${this.state.error}
          <button class="btn btn-secondary" style="margin-left: 1rem;" onclick="this.getRootNode().host.refreshData()">
            Retry
          </button>
        </div>
      `;
    }

    if (this.state.sessions.length === 0) {
      return `
        <div class="empty-state">
          <svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
          </svg>
          <h3>No demo sessions found</h3>
          <p>Create your first demo scenario to see resources here.</p>
        </div>
      `;
    }

    return `
      <div class="sessions-grid">
        ${this.state.sessions.map(session => this.renderSessionCard(session)).join("")}
      </div>
    `;
  }

  renderSessionCard(session) {
    const isCleaningUp = this.state.cleanupInProgress.has(session.id);
    const createdAt = new Date(session.created_at).toLocaleDateString();
    const resourceCount = session.resource_count || 0;

    // Create a more descriptive title using parameters
    const displayTitle = this.generateSessionTitle(session);
    const scenarioDisplayName = session.scenario_id.replace(/-/g, " ").replace(/\b\w/g, l => l.toUpperCase());

    return `
      <div class="session-card">
        <div class="session-header">
          <div class="session-title">${displayTitle}</div>
          <div class="session-scenario">${scenarioDisplayName}</div>
        </div>

        <div class="session-meta">
          <div class="session-created">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12,6 12,12 16,14"/>
            </svg>
            Created ${createdAt}
          </div>
        </div>

        <div class="session-resources">
          <div class="resource-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
            ${resourceCount} resource${resourceCount !== 1 ? "s" : ""}
          </div>
        </div>

        <div class="session-actions">
          <button
            class="btn btn-secondary"
            data-action="view-resources"
            data-session-id="${session.id}"
            ${isCleaningUp ? "disabled" : ""}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            View Details
          </button>

          <button
            class="btn btn-primary"
            data-action="confirm-cleanup"
            data-session-id="${session.id}"
            data-scenario-id="${session.scenario_id}"
            ${isCleaningUp || resourceCount === 0 ? "disabled" : ""}
          >
            ${isCleaningUp ? `
              <svg class="btn-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 11-6.219-8.56"/>
              </svg>
              Cleaning...
            ` : `
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3,6 5,6 21,6"/>
                <path d="m19,6v14a2,2 0 0,1-2,2H7a2,2 0 0,1-2-2V6m3,0V4a2,2 0 0,1,2-2h4a2,2 0 0,1,2,2v2"/>
              </svg>
              Clean Up
            `}
          </button>
        </div>
      </div>
    `;
  }

  generateSessionTitle(session) {
    // Create a descriptive title using parameters and session info
    const params = session.parameters || {};
    const scenarioName = session.scenario_id.replace(/-/g, " ").replace(/\b\w/g, l => l.toUpperCase());

    // Try to find meaningful identifiers in parameters
    const appName = params.application_name || params.app_name || params.name;
    const repoName = params.repository_name || params.repo_name;
    const componentName = params.component_name;
    const organizationName = params.organization_name || params.org_name;

    // Create title with most specific identifier available
    if (appName) {
      return `${scenarioName}: ${appName}`;
    } else if (repoName) {
      return `${scenarioName}: ${repoName}`;
    } else if (componentName) {
      return `${scenarioName}: ${componentName}`;
    } else if (organizationName) {
      return `${scenarioName} (${organizationName})`;
    } else {
      // Fallback to scenario + creation time for uniqueness
      const shortId = session.id.slice(-8); // Last 8 chars of session ID
      return `${scenarioName} (${shortId})`;
    }
  }

  setupEventListeners() {
    // Only set up event listeners once to prevent multiple handlers
    if (this._eventListenersSetup) {
      return;
    }

    // Handle button clicks using event delegation
    this.shadowRoot.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;

      // Prevent default and stop propagation to avoid multiple triggers
      event.preventDefault();
      event.stopPropagation();

      const action = button.getAttribute('data-action');
      const sessionId = button.getAttribute('data-session-id');
      const scenarioId = button.getAttribute('data-scenario-id');

      if (button.disabled) return;

      switch (action) {
        case 'view-resources':
          this.viewResources(sessionId);
          break;
        case 'confirm-cleanup':
          this.confirmCleanup(sessionId, scenarioId);
          break;
      }
    });

    this._eventListenersSetup = true;
  }

  async refreshData() {
    if (!this.userEmail) {
      this.state.error = "No user email provided";
      this.render();
      return;
    }

    this.state.loading = true;
    this.state.error = null;
    this.render();

    try {
      const response = await fetch(`/api/my/sessions`, {
        headers: {
          'X-User-Email': this.userEmail
        }
      });

      // Parse response once, regardless of status
      let responseData;
      try {
        responseData = await response.json();
      } catch (jsonError) {
        console.error('Failed to parse response as JSON:', jsonError);
        throw new Error(`Failed to fetch sessions: Invalid response format`);
      }

      if (!response.ok) {
        const errorMessage = responseData.detail || `Failed to fetch sessions: ${response.statusText}`;
        throw new Error(errorMessage);
      }

      this.state.sessions = responseData;
      this.state.loading = false;

      // Update tab badge if parent has tab navigation
      this.updateTabBadge();

    } catch (error) {
      this.state.error = error.message;
      this.state.loading = false;
    }

    this.render();
  }

  updateTabBadge() {
    const totalResources = this.state.sessions.reduce((sum, session) => sum + (session.resource_count || 0), 0);

    // Dispatch a custom event instead of DOM traversal
    this.dispatchEvent(new CustomEvent('badge-update', {
      detail: {
        tabId: 'cleanup',
        count: totalResources
      },
      bubbles: true
    }));
  }

  confirmCleanup(sessionId, scenarioId) {
    const dialog = document.createElement("div");
    dialog.className = "cleanup-confirmation";
    dialog.innerHTML = `
      <div class="confirmation-dialog">
        <div class="confirmation-header">
          <div class="confirmation-title">Confirm Cleanup</div>
        </div>
        <p>Are you sure you want to clean up all resources in the <strong>${scenarioId}</strong> scenario?</p>
        <p>This action cannot be undone and will delete:</p>
        <ul style="margin: 1rem 0; padding-left: 1.5rem;">
          <li>GitHub repositories</li>
          <li>CloudBees components</li>
          <li>CloudBees environments</li>
          <li>CloudBees applications</li>
        </ul>
        <div class="confirmation-actions">
          <button class="btn btn-secondary" onclick="this.parentElement.parentElement.parentElement.remove()">
            Cancel
          </button>
          <button class="btn btn-primary" onclick="this.getRootNode().querySelector('cleanup-dashboard').handleCleanup('${sessionId}'); this.parentElement.parentElement.parentElement.remove();">
            Yes, Clean Up
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);
  }

  async handleCleanup(sessionId) {
    this.state.cleanupInProgress.add(sessionId);
    this.render();

    try {
      const response = await fetch(`/api/sessions/${sessionId}`, {
        method: "DELETE",
        headers: {
          'X-User-Email': this.userEmail
        }
      });

      // Parse response once, regardless of status
      let responseData;
      try {
        responseData = await response.json();
      } catch (jsonError) {
        console.error('Failed to parse cleanup response as JSON:', jsonError);
        throw new Error(`Cleanup failed: Invalid response format`);
      }

      if (!response.ok) {
        const errorMessage = responseData.detail || `Cleanup failed: ${response.statusText}`;
        throw new Error(errorMessage);
      }

      const result = responseData;

      // Show success message
      this.showStatusMessage(
        `Successfully cleaned up ${result.successful} of ${result.total_resources} resources`,
        result.success ? "success" : "error"
      );

      if (result.errors.length > 0) {
        console.warn("Cleanup errors:", result.errors);
      }

      // Refresh data after cleanup
      await this.refreshData();

    } catch (error) {
      this.showStatusMessage(`Cleanup failed: ${error.message}`, "error");
    } finally {
      this.state.cleanupInProgress.delete(sessionId);
      this.render();
    }
  }

  async viewResources(sessionId) {
    try {
      const response = await fetch(`/api/sessions/${sessionId}/resources`, {
        headers: {
          'X-User-Email': this.userEmail
        }
      });

      // Parse response once, regardless of status
      let responseData;
      try {
        responseData = await response.json();
      } catch (jsonError) {
        console.error('Failed to parse resources response as JSON:', jsonError);
        throw new Error(`Failed to fetch resources: Invalid response format`);
      }

      if (!response.ok) {
        const errorMessage = responseData.detail || `Failed to fetch resources: ${response.statusText}`;
        throw new Error(errorMessage);
      }

      const resources = responseData;

      // Create a simple modal showing resources
      const dialog = document.createElement("div");
      dialog.className = "cleanup-confirmation";
      dialog.innerHTML = `
        <div class="confirmation-dialog" style="max-width: 600px;">
          <div class="confirmation-header">
            <div class="confirmation-title" style="color: #1f2937;">Session Resources</div>
          </div>
          <div class="resource-details-content">
            ${resources.length === 0 ?
              "<p class='no-resources-message'>No resources found in this session.</p>" :
              `<div class="resource-list">
                ${resources.map(resource => `
                  <div class="resource-item">
                    <div class="resource-info">
                      <div class="resource-name">${resource.resource_name}</div>
                      <div class="resource-type">${resource.resource_type.replace(/_/g, " ")}</div>
                    </div>
                    <div class="resource-meta">
                      <span class="resource-badge ${resource.platform}">${resource.platform}</span>
                      <span class="resource-status status-${resource.status}">${resource.status}</span>
                    </div>
                  </div>
                `).join("")}
              </div>`
            }
          </div>
          <div class="confirmation-actions">
            <button class="btn btn-secondary" onclick="this.parentElement.parentElement.parentElement.remove()">
              Close
            </button>
          </div>
        </div>
      `;

      document.body.appendChild(dialog);

    } catch (error) {
      this.showStatusMessage(`Failed to load resources: ${error.message}`, "error");
    }
  }

  showStatusMessage(message, type) {
    const statusContainer = this.shadowRoot.getElementById("status-messages");
    const statusDiv = document.createElement("div");
    statusDiv.className = `status-message status-${type}`;
    statusDiv.textContent = message;

    statusContainer.appendChild(statusDiv);

    // Remove after 5 seconds
    setTimeout(() => {
      statusDiv.remove();
    }, 5000);
  }
}

// Register the web component
customElements.define("cleanup-dashboard", CleanupDashboard);

// Export for use in other scripts
window.CleanupDashboard = CleanupDashboard;