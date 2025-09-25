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
  }

  connectedCallback() {
    this.render();
    this.refreshData();

    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(this.refreshData, 30000);

    // Listen for tab changes to refresh data when tab becomes active
    document.addEventListener('tab-change', (event) => {
      if (event.detail.activeTab === 'cleanup') {
        // Small delay to ensure DOM is ready
        setTimeout(() => this.refreshData(), 100);
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

        .loading-state {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 3rem;
          color: #6b7280;
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

        .resource-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
          padding: 0.25rem 0.5rem;
          background: #f3f4f6;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 500;
          color: #374151;
        }

        .resource-badge.github {
          background: #f0f9ff;
          color: #1e40af;
        }

        .resource-badge.cloudbees {
          background: #ecfdf5;
          color: #065f46;
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

        .cleanup-confirmation {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .confirmation-dialog {
          background: white;
          border-radius: 0.75rem;
          padding: 1.5rem;
          max-width: 400px;
          width: 90%;
          box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1);
        }

        .confirmation-header {
          margin-bottom: 1rem;
        }

        .confirmation-title {
          font-size: 1.125rem;
          font-weight: 600;
          color: #dc2626;
          margin-bottom: 0.5rem;
        }

        .confirmation-actions {
          display: flex;
          gap: 0.75rem;
          justify-content: flex-end;
          margin-top: 1.5rem;
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
        <div class="loading-state">
          <svg class="btn-spinner" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
          </svg>
          <span style="margin-left: 0.5rem;">Loading sessions...</span>
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

    return `
      <div class="session-card">
        <div class="session-header">
          <div class="session-title">${session.scenario_id.replace(/-/g, " ").replace(/\\b\\w/g, l => l.toUpperCase())}</div>
          <div class="session-scenario">${session.scenario_id}</div>
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
            onclick="this.getRootNode().host.viewResources('${session.id}')"
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
            onclick="this.getRootNode().host.confirmCleanup('${session.id}', '${session.scenario_id}')"
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

  setupEventListeners() {
    // Event listeners are handled via onclick attributes for simplicity
    // in the shadow DOM context
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
    // Try to find parent tab navigation and update badge
    let parent = this.parentElement;
    while (parent) {
      if (parent.tagName === "TAB-NAVIGATION") {
        const totalResources = this.state.sessions.reduce((sum, session) => sum + (session.resource_count || 0), 0);
        parent.updateBadge("cleanup", totalResources);
        break;
      }
      parent = parent.parentElement;
    }
  }

  confirmCleanup(sessionId, scenarioId) {
    const dialog = document.createElement("div");
    dialog.className = "cleanup-confirmation";
    dialog.innerHTML = `
      <div class="confirmation-dialog">
        <div class="confirmation-header">
          <div class="confirmation-title">⚠️ Confirm Cleanup</div>
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
            <div class="confirmation-title" style="color: #1f2937;">📋 Session Resources</div>
          </div>
          <div style="max-height: 400px; overflow-y: auto;">
            ${resources.length === 0 ? "<p>No resources found in this session.</p>" : `
              <table style="width: 100%; font-size: 0.875rem;">
                <thead>
                  <tr style="border-bottom: 1px solid #e5e7eb;">
                    <th style="text-align: left; padding: 0.5rem;">Type</th>
                    <th style="text-align: left; padding: 0.5rem;">Name</th>
                    <th style="text-align: left; padding: 0.5rem;">Platform</th>
                    <th style="text-align: left; padding: 0.5rem;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${resources.map(resource => `
                    <tr style="border-bottom: 1px solid #f3f4f6;">
                      <td style="padding: 0.5rem;">${resource.resource_type.replace(/_/g, " ")}</td>
                      <td style="padding: 0.5rem;">${resource.resource_name}</td>
                      <td style="padding: 0.5rem;">
                        <span class="resource-badge ${resource.platform}">${resource.platform}</span>
                      </td>
                      <td style="padding: 0.5rem;">
                        <span style="color: ${resource.status === "active" ? "#059669" : "#dc2626"};">
                          ${resource.status}
                        </span>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            `}
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