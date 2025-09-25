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
    this.setupBadgeEventListeners();
    // Apply initial tab states to content panels
    this.updateTabStates();
  }

  static get observedAttributes() {
    return ["tabs", "default-tab"];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this.initialize();
      this.render();
      this.setupEventListeners();
      // Make sure initial tab state is applied to content panels
      this.updateTabStates();
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
          display: flex;
          gap: 0.5rem;
        }

        .tab-button {
          padding: 0.5rem 1rem;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          color: #6b7280;
          cursor: pointer;
          transition: all 0.2s ease;
          text-decoration: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          white-space: nowrap;
          min-width: 120px;
        }

        .tab-button:hover {
          background: #f3f4f6;
          color: #374151;
        }

        .tab-button:focus {
          outline: 2px solid #806FF6;
          outline-offset: -2px;
        }

        .tab-button.active {
          background: #f3f4f6;
          color: #1f2937;
          border-color: #d1d5db;
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
    `;
  }

  setupEventListeners() {
    const tabButtons = this.shadowRoot.querySelectorAll(".tab-button");
    tabButtons.forEach((button) => {
      button.addEventListener("click", this.handleTabClick);
      button.addEventListener("keydown", this.handleKeyDown);
    });
  }

  setupBadgeEventListeners() {
    // Listen for badge update events from child components
    document.addEventListener('badge-update', (event) => {
      if (event.detail && event.detail.tabId && typeof event.detail.count !== 'undefined') {
        this.updateBadge(event.detail.tabId, event.detail.count);
      }
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

    // Update tab button states
    tabButtons.forEach((button) => {
      const tabId = button.getAttribute("data-tab-id");
      const isActive = tabId === this.state.activeTab;

      button.classList.toggle("active", isActive);
      button.setAttribute("aria-selected", isActive.toString());
      button.setAttribute("tabindex", isActive ? "0" : "-1");
    });

    // Update external content panels - first hide all, then show active
    const contentPanels = document.querySelectorAll(".content-panel");

    if (contentPanels.length === 0) {
      console.warn("No content panels found for tab navigation");
      return;
    }

    // First pass: remove active from all panels
    contentPanels.forEach((panel) => {
      if (panel && typeof panel.classList !== 'undefined') {
        panel.classList.remove("active");
      }
    });

    // Second pass: add active to the target panel
    if (this.state.activeTab) {
      const activePanel = document.querySelector(`#panel-${this.state.activeTab}`);
      if (activePanel && typeof activePanel.classList !== 'undefined') {
        activePanel.classList.add("active");
      } else if (this.state.activeTab !== 'undefined') {
        console.warn(`Target panel not found: #panel-${this.state.activeTab}`);
      }
    }
  }

  // Public API methods
  getActiveTab() {
    return this.state.activeTab;
  }

  updateBadge(tabId, count) {
    const tab = this.state.tabs.find((t) => t.id === tabId);
    if (tab) {
      tab.badge = count;

      // Update only the specific badge element instead of full re-render
      const tabButton = this.shadowRoot.querySelector(`[data-tab-id="${tabId}"]`);
      if (tabButton) {
        const badge = tabButton.querySelector('.tab-badge');
        if (badge) {
          badge.textContent = count;
          badge.classList.toggle('zero', count === 0);
        }
      }
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