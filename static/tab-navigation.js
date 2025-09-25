/**
 * Tab Navigation Web Component
 * Provides reusable tabbed interface with accessible keyboard navigation
 */
class TabNavigation extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    this.state = {
      activeTab: null,
      tabs: [],
    };

    this.handleTabClick = this.handleTabClick.bind(this);
    this.handleKeyDown = this.handleKeyDown.bind(this);
  }

  connectedCallback() {
    this.initialize();
    this.render();
    this.setupEventListeners();
  }

  static get observedAttributes() {
    return ["tabs", "default-tab"];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this.initialize();
      this.render();
    }
  }

  initialize() {
    // Parse tabs from attribute
    try {
      const tabsAttr = this.getAttribute("tabs");
      this.state.tabs = tabsAttr ? JSON.parse(tabsAttr) : [];
    } catch (e) {
      console.error("Invalid tabs JSON:", e);
      this.state.tabs = [];
    }

    // Set default active tab
    const defaultTab = this.getAttribute("default-tab");
    this.state.activeTab = defaultTab || (this.state.tabs[0]?.id);
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
        }

        .tab-container {
          display: flex;
          flex-direction: column;
          width: 100%;
        }

        .tab-nav {
          display: flex;
          border-bottom: 2px solid #e5e7eb;
          margin-bottom: 1.5rem;
          gap: 0.5rem;
        }

        .tab-button {
          background: none;
          border: none;
          padding: 0.75rem 1.5rem;
          font-size: 1rem;
          font-weight: 500;
          color: #6b7280;
          cursor: pointer;
          border-bottom: 3px solid transparent;
          transition: all 0.2s ease;
          position: relative;
        }

        .tab-button:hover {
          color: #374151;
          background-color: #f9fafb;
        }

        .tab-button:focus {
          outline: 2px solid #3b82f6;
          outline-offset: -2px;
        }

        .tab-button.active {
          color: #1f2937;
          border-bottom-color: #3b82f6;
          font-weight: 600;
        }

        .tab-content {
          width: 100%;
        }

        .tab-panel {
          display: none;
          width: 100%;
        }

        .tab-panel.active {
          display: block;
        }

        /* Badge styling for tab buttons */
        .tab-badge {
          background: #dc2626;
          color: white;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.125rem 0.375rem;
          border-radius: 9999px;
          margin-left: 0.5rem;
          min-width: 1.25rem;
          text-align: center;
        }

        .tab-badge.zero {
          display: none;
        }
      </style>

      <div class="tab-container">
        <nav class="tab-nav" role="tablist" aria-label="Main navigation">
          ${this.state.tabs
            .map(
              (tab, index) => `
            <button
              class="tab-button ${tab.id === this.state.activeTab ? "active" : ""}"
              role="tab"
              tabindex="${tab.id === this.state.activeTab ? "0" : "-1"}"
              aria-selected="${tab.id === this.state.activeTab ? "true" : "false"}"
              aria-controls="panel-${tab.id}"
              data-tab-id="${tab.id}"
              data-tab-index="${index}"
            >
              ${tab.label}
              ${tab.badge !== undefined ? `<span class="tab-badge ${tab.badge === 0 ? "zero" : ""}">${tab.badge}</span>` : ""}
            </button>
          `,
            )
            .join("")}
        </nav>

        <div class="tab-content">
          ${this.state.tabs
            .map(
              (tab) => `
            <div
              class="tab-panel ${tab.id === this.state.activeTab ? "active" : ""}"
              role="tabpanel"
              id="panel-${tab.id}"
              aria-labelledby="tab-${tab.id}"
            >
              <slot name="${tab.id}"></slot>
            </div>
          `,
            )
            .join("")}
        </div>
      </div>
    `;
  }

  setupEventListeners() {
    const tabButtons = this.shadowRoot.querySelectorAll(".tab-button");
    tabButtons.forEach((button) => {
      button.addEventListener("click", this.handleTabClick);
      button.addEventListener("keydown", this.handleKeyDown);
    });
  }

  handleTabClick(event) {
    const tabId = event.currentTarget.getAttribute("data-tab-id");
    this.setActiveTab(tabId);
  }

  handleKeyDown(event) {
    const tabButtons = Array.from(this.shadowRoot.querySelectorAll(".tab-button"));
    const currentIndex = parseInt(event.currentTarget.getAttribute("data-tab-index"));

    switch (event.key) {
      case "ArrowLeft":
        event.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : tabButtons.length - 1;
        tabButtons[prevIndex].focus();
        break;

      case "ArrowRight":
        event.preventDefault();
        const nextIndex = currentIndex < tabButtons.length - 1 ? currentIndex + 1 : 0;
        tabButtons[nextIndex].focus();
        break;

      case "Home":
        event.preventDefault();
        tabButtons[0].focus();
        break;

      case "End":
        event.preventDefault();
        tabButtons[tabButtons.length - 1].focus();
        break;

      case "Enter":
      case " ":
        event.preventDefault();
        this.handleTabClick(event);
        break;
    }
  }

  setActiveTab(tabId) {
    if (this.state.activeTab === tabId) return;

    const oldTab = this.state.activeTab;
    this.state.activeTab = tabId;

    // Update UI
    this.updateTabStates();

    // Dispatch custom event
    this.dispatchEvent(
      new CustomEvent("tab-change", {
        detail: {
          activeTab: tabId,
          previousTab: oldTab,
        },
        bubbles: true,
      }),
    );
  }

  updateTabStates() {
    const tabButtons = this.shadowRoot.querySelectorAll(".tab-button");
    const tabPanels = this.shadowRoot.querySelectorAll(".tab-panel");

    tabButtons.forEach((button) => {
      const tabId = button.getAttribute("data-tab-id");
      const isActive = tabId === this.state.activeTab;

      button.classList.toggle("active", isActive);
      button.setAttribute("aria-selected", isActive.toString());
      button.setAttribute("tabindex", isActive ? "0" : "-1");
    });

    tabPanels.forEach((panel) => {
      const tabId = panel.id.replace("panel-", "");
      const isActive = tabId === this.state.activeTab;
      panel.classList.toggle("active", isActive);
    });
  }

  // Public API methods
  getActiveTab() {
    return this.state.activeTab;
  }

  updateBadge(tabId, count) {
    const tab = this.state.tabs.find((t) => t.id === tabId);
    if (tab) {
      tab.badge = count;
      this.render();
      this.setupEventListeners();
    }
  }

  addTab(tab) {
    this.state.tabs.push(tab);
    this.render();
    this.setupEventListeners();
  }

  removeTab(tabId) {
    this.state.tabs = this.state.tabs.filter((tab) => tab.id !== tabId);
    if (this.state.activeTab === tabId && this.state.tabs.length > 0) {
      this.state.activeTab = this.state.tabs[0].id;
    }
    this.render();
    this.setupEventListeners();
  }
}

// Register the web component
customElements.define("tab-navigation", TabNavigation);

// Export for use in other scripts
window.TabNavigation = TabNavigation;