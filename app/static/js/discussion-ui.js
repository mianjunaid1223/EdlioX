/**
 * Discussion UI Component
 * Handles all DOM interactions and rendering
 */

const DiscussionUI = {
  /**
   * Initialize UI components and event listeners
   */
  init() {
    this.setupEventListeners();
    this.initUIState();
    
    // Set up intersection observer for lazy loading
    this.setupLazyLoading();
    
    // If there's a specific discussion ID, show it
    if (DiscussionState.currentDiscussionId) {
      this.showSingleDiscussion(DiscussionState.currentDiscussionId);
    } else {
      // Otherwise show the discussions list
      DiscussionAPI.getDiscussions();
    }
  },
  
  /**
   * Set up event listeners
   */
  setupEventListeners() {
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    
    if (searchInput) {
      searchInput.addEventListener('input', this.handleSearchInput.bind(this));
      searchInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          this.handleSearch();
        }
      });
    }
    
    if (searchButton) {
      searchButton.addEventListener('click', this.handleSearch.bind(this));
    }
    
    // Sort buttons
    document.querySelectorAll('.sort-btn').forEach(btn => {
      btn.addEventListener('click', this.handleSort.bind(this));
    });
    
    // Filter controls
    const subjectFilter = document.getElementById('subjectFilter');
    const gradeFilter = document.getElementById('gradeFilter');
    const applyFiltersBtn = document.getElementById('applyFiltersBtn');
    
    if (applyFiltersBtn) {
      applyFiltersBtn.addEventListener('click', this.handleFilters.bind(this));
    }
    
    // Create discussion button and form
    const createBtn = document.getElementById('createDiscussionBtn');
    const createForm = document.getElementById('createDiscussionForm');
    const cancelBtn = document.getElementById('cancelDiscussionBtn');
    
    if (createBtn) {
      createBtn.addEventListener('click', this.showCreateDiscussionModal.bind(this));
    }
    
    if (createForm) {
      createForm.addEventListener('submit', this.handleCreateDiscussion.bind(this));
    }
    
    if (cancelBtn) {
      cancelBtn.addEventListener('click', this.hideCreateDiscussionModal.bind(this));
    }
    
    // Handle browser navigation
    window.addEventListener('popstate', this.handleNavigation.bind(this));
    
    // Dark mode toggle
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
      darkModeToggle.addEventListener('click', this.toggleDarkMode.bind(this));
    }
  },
  
  /**
   * Initialize UI state based on saved preferences
   */
  initUIState() {
    // Set search input value
    const searchInput = document.getElementById('searchInput');
    if (searchInput && DiscussionState.currentSearch) {
      searchInput.value = DiscussionState.currentSearch;
    }
    
    // Set active sort button
    document.querySelectorAll('.sort-btn').forEach(btn => {
      if (btn.dataset.sort === DiscussionState.currentSort) {
        btn.classList.add('active');
        
        // Add checkmark icon if not present
        if (!btn.querySelector('.fa-check')) {
          const checkIcon = document.createElement('i');
          checkIcon.className = 'fas fa-check text-primary';
          btn.appendChild(checkIcon);
        }
      } else {
        btn.classList.remove('active');
        const checkIcon = btn.querySelector('.fa-check');
        if (checkIcon) {
          checkIcon.remove();
        }
      }
    });
    
    // Set filter values
    const subjectFilter = document.getElementById('subjectFilter');
    const gradeFilter = document.getElementById('gradeFilter');
    
    if (subjectFilter && DiscussionState.subject) {
      subjectFilter.value = DiscussionState.subject;
    }
    
    if (gradeFilter && DiscussionState.gradeLevel) {
      gradeFilter.value = DiscussionState.gradeLevel;
    }
    
    // Check for dark mode preference
    this.initDarkMode();
  },
  
  /**
   * Initialize dark mode based on saved preference
   */
  initDarkMode() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (!darkModeToggle) return;
    
    const moonIcon = darkModeToggle.querySelector('.dark-icon');
    const sunIcon = darkModeToggle.querySelector('.light-icon');
    
    if (localStorage.theme === 'dark' || 
        (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark-mode');
      if (moonIcon) moonIcon.classList.remove('d-none');
      if (sunIcon) sunIcon.classList.add('d-none');
    } else {
      document.documentElement.classList.remove('dark-mode');
      if (moonIcon) moonIcon.classList.add('d-none');
      if (sunIcon) sunIcon.classList.remove('d-none');
    }
  },
  
  /**
   * Toggle dark mode
   */
  toggleDarkMode() {
    const htmlEl = document.documentElement;
    htmlEl.classList.toggle('dark-mode');
    
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (!darkModeToggle) return;
    
    const moonIcon = darkModeToggle.querySelector('.dark-icon');
    const sunIcon = darkModeToggle.querySelector('.light-icon');
    
    if (htmlEl.classList.contains('dark-mode')) {
      localStorage.theme = 'dark';
      if (moonIcon) moonIcon.classList.remove('d-none');
      if (sunIcon) sunIcon.classList.add('d-none');
    } else {
      localStorage.theme = 'light';
      if (moonIcon) moonIcon.classList.add('d-none');
      if (sunIcon) sunIcon.classList.remove('d-none');
    }
  },
  
  /**
   * Handle search input with debouncing
   */
  handleSearchInput(e) {
    const query = e.target.value.trim();
    
    // Clear previous timer
    if (DiscussionState.searchDebounceTimer) {
      clearTimeout(DiscussionState.searchDebounceTimer);
    }
    
    // Set new timer for debouncing
    DiscussionState.searchDebounceTimer = setTimeout(() => {
      if (query.length >= 3 || query.length === 0) {
        DiscussionState.currentSearch = query;
        DiscussionState.resetPagination();
        DiscussionState.saveToCache();
        DiscussionAPI.getDiscussions();
      }
    }, 500); // 500ms debounce
  },
  
  /**
   * Handle search button click or Enter key
   */
  handleSearch() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput?.value.trim() || '';
    
    DiscussionState.currentSearch = query;
    DiscussionState.resetPagination();
    DiscussionState.saveToCache();
    DiscussionAPI.getDiscussions();
  },
  
  /**
   * Handle sort button click
   */
  handleSort(e) {
    const button = e.currentTarget;
    const sortBy = button.dataset.sort;
    
    if (sortBy === DiscussionState.currentSort) {
      return; // Already selected
    }
    
    // Update active button styling
    document.querySelectorAll('.sort-btn').forEach(btn => {
      btn.classList.remove('active');
      const icon = btn.querySelector('.fa-check');
      if (icon) icon.remove();
    });
    
    button.classList.add('active');
    
    // Add checkmark icon
    if (!button.querySelector('.fa-check')) {
      const checkIcon = document.createElement('i');
      checkIcon.className = 'fas fa-check text-primary';
      button.appendChild(checkIcon);
    }
    
    // Update state and fetch data
    DiscussionState.currentSort = sortBy;
    DiscussionState.resetPagination();
    DiscussionState.saveToCache();
    DiscussionAPI.getDiscussions();
  },
  
  /**
   * Handle filter button click
   */
  handleFilters() {
    const subjectFilter = document.getElementById('subjectFilter');
    const gradeFilter = document.getElementById('gradeFilter');
    
    DiscussionState.subject = subjectFilter?.value || '';
    DiscussionState.gradeLevel = gradeFilter?.value || '';
    DiscussionState.resetPagination();
    DiscussionState.saveToCache();
    DiscussionAPI.getDiscussions();
  },
  
  /**
   * Set up lazy loading with Intersection Observer
   */
  setupLazyLoading() {
    if (!('IntersectionObserver' in window)) return;
    
    // Create observer for pagination
    const paginationObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const nextPageTrigger = entry.target;
          
          // Load more content when pagination trigger is visible
          if (nextPageTrigger.dataset.hasMore === 'true' && !DiscussionState.isLoading) {
            DiscussionState.currentPage++;
            DiscussionAPI.getDiscussions();
          }
          
          // Unobserve after triggering
          paginationObserver.unobserve(nextPageTrigger);
        }
      });
    }, { rootMargin: '200px' });
    
    // Observer for images and avatars
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const lazyImage = entry.target;
          if (lazyImage.dataset.src) {
            lazyImage.src = lazyImage.dataset.src;
            lazyImage.removeAttribute('data-src');
          }
          imageObserver.unobserve(lazyImage);
        }
      });
    });
    
    // Attach observers after content is loaded
    document.addEventListener('DOMContentLoaded', () => {
      // Set up pagination observer
      const paginationTrigger = document.getElementById('paginationTrigger');
      if (paginationTrigger) {
        paginationObserver.observe(paginationTrigger);
      }
      
      // Set up image observer
      document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
      });
    });
    
    // Store observers for reuse
    this.observers = {
      pagination: paginationObserver,
      images: imageObserver
    };
  },
  
  /**
   * Show create discussion modal
   */
  showCreateDiscussionModal() {
    const modal = document.getElementById('createDiscussionModal');
    if (!modal) return;
    
    try {
      const bsModal = new bootstrap.Modal(modal);
      bsModal.show();
    } catch (error) {
      console.error('Bootstrap modal error:', error);
      // Fallback method
      modal.classList.add('show');
      modal.style.display = 'block';
      document.body.classList.add('modal-open');
      
      const backdrop = document.createElement('div');
      backdrop.className = 'modal-backdrop fade show';
      document.body.appendChild(backdrop);
    }
  },
  
  /**
   * Hide create discussion modal
   */
  hideCreateDiscussionModal() {
    const modal = document.getElementById('createDiscussionModal');
    if (!modal) return;
    
    try {
      const bsModal = bootstrap.Modal.getInstance(modal);
      if (bsModal) bsModal.hide();
    } catch (error) {
      console.error('Bootstrap modal error:', error);
      // Fallback method
      modal.classList.remove('show');
      modal.style.display = 'none';
      document.body.classList.remove('modal-open');
      
      const backdrop = document.querySelector('.modal-backdrop');
      if (backdrop) backdrop.remove();
    }
    
    // Reset form
    const form = document.getElementById('createDiscussionForm');
    if (form) form.reset();
  },
  
  /**
   * Handle create discussion form submission
   */
  async handleCreateDiscussion(e) {
    e.preventDefault();
    
    if (!DiscussionState.userId) {
      this.showError('You must be logged in to create a discussion');
      return;
    }
    
    const form = e.target;
    const title = form.elements.title.value.trim();
    const content = form.elements.content.value.trim();
    const subject = form.elements.subject?.value || 'General';
    const gradeLevel = form.elements.grade_level?.value || 'General';
    
    if (!title) {
      this.showError('Title cannot be empty');
      return;
    }
    
    if (!content) {
      this.showError('Content cannot be empty');
      return;
    }
    
    try {
      // Disable form during submission
      this.setFormDisabled(form, true);
      
      const data = await DiscussionAPI.createDiscussion({
        title,
        content,
        subject,
        grade_level: gradeLevel
      });
      
      // Success! Hide modal and reset form
      this.hideCreateDiscussionModal();
      this.showSuccess('Discussion created successfully!');
      
      // Navigate to the new discussion
      this.showSingleDiscussion(data.id);
    } catch (error) {
      this.showError(error.message || 'Failed to create discussion');
    } finally {
      this.setFormDisabled(form, false);
    }
  },
  
  /**
   * Enable/disable a form during submission
   */
  setFormDisabled(form, disabled) {
    if (!form) return;
    
    const elements = form.elements;
    for (let i = 0; i < elements.length; i++) {
      elements[i].disabled = disabled;
    }
    
    // Update submit button with spinner
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      if (disabled) {
        const originalText = submitBtn.innerHTML;
        submitBtn.dataset.originalText = originalText;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Processing...';
      } else {
        const originalText = submitBtn.dataset.originalText;
        if (originalText) {
          submitBtn.innerHTML = originalText;
        }
      }
    }
  },
  
  /**
   * Display discussions in a list
   */
  renderDiscussions(data) {
    const discussionsList = document.getElementById('discussionsList');
    if (!discussionsList) return;
    
    // Clear loading state
    discussionsList.innerHTML = '';
    
    if (!data.discussions || data.discussions.length === 0) {
      this.showEmptyDiscussionsState();
      return;
    }
    
    // Show discussions
    discussionsList.classList.remove('d-none');
    document.getElementById('singleDiscussionView')?.classList.add('d-none');
    document.getElementById('pagination')?.classList.remove('d-none');
    
    data.discussions.forEach(discussion => {
      discussionsList.appendChild(this.createDiscussionElement(discussion));
    });
    
    // Update pagination
    this.updatePagination(data);
  },
  
  /**
   * Create a discussion list item element
   */
  createDiscussionElement(discussion) {
    const element = document.createElement('div');
    element.className = 'card shadow-sm mb-4 hover-shadow';
    
    const userInitial = discussion.username ? discussion.username.charAt(0).toUpperCase() : 'A';
    const hasVoted = DiscussionState.userId ? 
                     (discussion.votes?.up?.includes(DiscussionState.userId) ? 'up' : 
                      discussion.votes?.down?.includes(DiscussionState.userId) ? 'down' : null) : null;
    
    element.innerHTML = `
      <div class="card-body p-4">
        <div class="row g-3">
          <!-- Vote Controls -->
          <div class="col-auto">
            <div class="d-flex flex-column align-items-center bg-light rounded p-2">
              <button class="vote-btn upvote btn btn-sm btn-light rounded-circle mb-1 ${hasVoted === 'up' ? 'text-primary' : 'text-secondary'}" 
                      data-id="${discussion.id}" data-type="discussion">
                <i class="fas fa-chevron-up"></i>
              </button>
              <span class="score fw-medium">${discussion.score || 0}</span>
              <button class="vote-btn downvote btn btn-sm btn-light rounded-circle mt-1 ${hasVoted === 'down' ? 'text-danger' : 'text-secondary'}" 
                      data-id="${discussion.id}" data-type="discussion">
                <i class="fas fa-chevron-down"></i>
              </button>
            </div>
          </div>
          
          <!-- Main Content -->
          <div class="col">
            <h3 class="h5 mb-2">
              <a href="#" class="text-decoration-none discussion-title" data-id="${discussion.id}">
                ${this.escapeHtml(discussion.title)}
              </a>
            </h3>
            
            <div class="text-secondary mb-3 overflow-hidden" style="max-height: 4.5rem;">
              ${this.escapeHtml(discussion.content.substring(0, 200))}${discussion.content.length > 200 ? '...' : ''}
            </div>
            
            <div class="d-flex flex-wrap align-items-center gap-3 mt-3">
              <!-- Author & Date Info -->
              <div class="d-flex align-items-center gap-2">
                <div class="bg-secondary text-white rounded-circle d-flex align-items-center justify-content-center fs-5 fw-medium" 
                      style="width: 32px; height: 32px;">
                  ${userInitial}
                </div>
                <div>
                  <p class="mb-0 small fw-medium">${this.escapeHtml(discussion.username || 'Anonymous')}</p>
                  <p class="mb-0 text-muted fs-sm">${this.formatDate(discussion.created_at)}</p>
                </div>
              </div>
              
              <!-- Stats -->
              <div class="d-flex align-items-center gap-3 ms-auto">
                ${discussion.subject && discussion.subject !== 'General' ? 
                  `<span class="badge bg-primary-subtle text-primary d-flex align-items-center gap-1">
                    ${this.escapeHtml(discussion.subject)}
                  </span>` : ''}
                  
                <span class="badge bg-light text-secondary d-flex align-items-center gap-1">
                  <i class="fas fa-comment-alt"></i>
                  ${discussion.comment_count || 0}
                </span>
                <span class="badge bg-light text-secondary d-flex align-items-center gap-1">
                  <i class="fas fa-eye"></i>
                  ${discussion.views || 0}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Add event listeners
    const discussionTitle = element.querySelector('.discussion-title');
    if (discussionTitle) {
      discussionTitle.addEventListener('click', (e) => {
        e.preventDefault();
        this.showSingleDiscussion(discussion.id);
      });
    }
    
    // Add vote button event listeners
    const voteButtons = element.querySelectorAll('.vote-btn');
    voteButtons.forEach(btn => {
      btn.addEventListener('click', this.handleVote.bind(this));
    });
    
    return element;
  },
  
  // More methods will be implemented in the next file chunk...
  
  /**
   * Show loading state for discussions list
   */
  showDiscussionsLoading() {
    const discussionsList = document.getElementById('discussionsList');
    if (!discussionsList) return;
    
    discussionsList.innerHTML = `
      <div class="card shadow-sm mb-4">
        <div class="card-body p-5">
          <div class="row mb-4">
            <div class="col-auto">
              <div class="skeleton" style="width: 40px; height: 80px;"></div>
            </div>
            <div class="col">
              <div class="skeleton skeleton-title"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text"></div>
            </div>
          </div>
          <div class="row mb-4">
            <div class="col-auto">
              <div class="skeleton" style="width: 40px; height: 80px;"></div>
            </div>
            <div class="col">
              <div class="skeleton skeleton-title"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text"></div>
            </div>
          </div>
        </div>
      </div>
    `;
  },
  
  /**
   * Show empty state for discussions list
   */
  showEmptyDiscussionsState() {
    const discussionsList = document.getElementById('discussionsList');
    if (!discussionsList) return;
    
    discussionsList.innerHTML = `
      <div class="card shadow-sm">
        <div class="card-body p-5 text-center">
          <i class="fas fa-comments text-secondary fa-3x mb-3"></i>
          <p class="fs-5 fw-medium text-secondary">No discussions found</p>
          ${DiscussionState.currentSearch ? `<p class="text-muted">Try a different search term</p>` : ''}
          ${DiscussionState.subject || DiscussionState.gradeLevel ? 
            `<p class="text-muted">Try removing some filters</p>` : ''}
          <button id="startNewDiscussionBtn" class="btn btn-primary mt-3">
            <i class="fas fa-plus me-2"></i> Start a New Discussion
          </button>
        </div>
      </div>
    `;
    
    // Add event listener to the new discussion button
    const newDiscussionBtn = document.getElementById('startNewDiscussionBtn');
    if (newDiscussionBtn) {
      newDiscussionBtn.addEventListener('click', this.showCreateDiscussionModal.bind(this));
    }
  },
  
  /**
   * Show error state for discussions list
   */
  showErrorState() {
    const discussionsList = document.getElementById('discussionsList');
    if (!discussionsList) return;
    
    discussionsList.innerHTML = `
      <div class="card shadow-sm">
        <div class="card-body p-5 text-center">
          <i class="fas fa-exclamation-triangle text-danger fa-3x mb-3"></i>
          <p class="fs-5 fw-medium text-danger">Failed to load discussions</p>
          <button id="retryLoadBtn" class="btn btn-primary mt-3">
            <i class="fas fa-sync-alt me-2"></i> Try Again
          </button>
        </div>
      </div>
    `;
    
    // Add retry button event listener
    const retryBtn = document.getElementById('retryLoadBtn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        DiscussionAPI.getDiscussions();
      });
    }
  },
  
  /**
   * Helper methods
   */
  escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },
  
  formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) {
      return 'just now';
    } else if (diffMin < 60) {
      return `${diffMin} min${diffMin !== 1 ? 's' : ''} ago`;
    } else if (diffHour < 24) {
      return `${diffHour} hr${diffHour !== 1 ? 's' : ''} ago`;
    } else if (diffDay < 7) {
      return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  },
  
  /**
   * Show a success toast notification
   */
  showSuccess(message) {
    this.showToast('success', message);
  },
  
  /**
   * Show an error toast notification
   */
  showError(message) {
    this.showToast('error', message);
  },
  
  /**
   * Show a toast notification
   */
  showToast(type, message) {
    const toastId = type === 'success' ? 'successToast' : 'errorToast';
    const messageId = type === 'success' ? 'successMessage' : 'errorMessage';
    
    const toast = document.getElementById(toastId);
    const messageEl = document.getElementById(messageId);
    
    if (!toast || !messageEl) return;
    
    messageEl.textContent = message;
    
    try {
      const bsToast = new bootstrap.Toast(toast);
      bsToast.show();
    } catch (error) {
      console.error('Bootstrap toast error:', error);
      // Fallback implementation
      toast.classList.add('show');
      toast.style.display = 'block';
      
      // Auto-hide after 5 seconds
      setTimeout(() => {
        toast.classList.remove('show');
        toast.style.display = 'none';
      }, 5000);
    }
  }
}; 