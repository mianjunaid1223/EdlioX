/**
 * Discussion System JavaScript
 * Enhanced for performance, reliability and memory efficiency
 */

// State management object with change tracking
const DiscussionState = {
  currentPage: 1,
  currentSort: 'score',
  currentSearch: '',
  currentDiscussionId: '',
  subject: '',
  gradeLevel: '',
  isLoading: false,
  userId: null,
  
  // For offline support
  discussionCache: {},
  pendingActions: [],
  
  // For debouncing
  searchDebounceTimer: null,
  
  /**
   * Initialize the state
   */
  init() {
    // Get user ID
    this.userId = document.querySelector('meta[name="user-id"]')?.content || null;
    
    // Get discussion ID from URL or data attribute
    const urlDiscussionId = new URLSearchParams(window.location.search).get('id') || 
                           window.location.pathname.match(/\/discussions\/([a-f0-9]+)/)?.[1] || 
                           document.getElementById('discussionContainer')?.dataset.discussionId;
    
    if (urlDiscussionId) {
      this.currentDiscussionId = urlDiscussionId;
    }
    
    // Load cached state from localStorage if available
    this.loadFromCache();
  },
  
  /**
   * Save current state to localStorage
   */
  saveToCache() {
    try {
      const cacheData = {
        currentSort: this.currentSort,
        currentSearch: this.currentSearch,
        subject: this.subject,
        gradeLevel: this.gradeLevel
      };
      localStorage.setItem('discussionState', JSON.stringify(cacheData));
    } catch (e) {
      console.warn('Failed to save state to localStorage:', e);
    }
  },
  
  /**
   * Load state from localStorage
   */
  loadFromCache() {
    try {
      const cached = localStorage.getItem('discussionState');
      if (cached) {
        const parsedData = JSON.parse(cached);
        this.currentSort = parsedData.currentSort || 'score';
        this.currentSearch = parsedData.currentSearch || '';
        this.subject = parsedData.subject || '';
        this.gradeLevel = parsedData.gradeLevel || '';
      }
    } catch (e) {
      console.warn('Failed to load state from localStorage:', e);
    }
  },
  
  /**
   * Reset pagination when filters change
   */
  resetPagination() {
    this.currentPage = 1;
  }
};

// API layer to handle all server communication
const DiscussionAPI = {
  /**
   * Get CSRF token from meta tag
   */
  getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  },
  
  /**
   * Fetch discussions with current filters
   */
  async getDiscussions() {
    if (DiscussionState.isLoading) return;
    
    DiscussionState.isLoading = true;
    
    // Build URL with query parameters
    const params = new URLSearchParams({
      page: DiscussionState.currentPage,
      sort_by: DiscussionState.currentSort,
      q: DiscussionState.currentSearch,
    });
    
    if (DiscussionState.subject) {
      params.append('subject', DiscussionState.subject);
    }
    
    if (DiscussionState.gradeLevel) {
      params.append('grade_level', DiscussionState.gradeLevel);
    }
    
    const url = `/discussions/api/discussions?${params.toString()}`;
    
    try {
      // Show loading UI
      DiscussionUI.showDiscussionsLoading();
      
      // Check cache for this exact request
      const cacheKey = url;
      const cachedResponse = this.checkCache(cacheKey);
      
      if (cachedResponse) {
        console.log('Using cached data for', url);
        DiscussionUI.renderDiscussions(cachedResponse);
        DiscussionState.isLoading = false;
        return;
      }
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('API Error Response:', errorText);
        throw new Error(`Failed to load discussions: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Cache the result (but not forever)
      this.cacheResponse(cacheKey, data, 300); // 5 minutes
      
      DiscussionUI.renderDiscussions(data);
    } catch (error) {
      console.error('Discussion loading error:', error);
      DiscussionUI.showError(error.message || 'Failed to load discussions');
      DiscussionUI.showErrorState();
    } finally {
      DiscussionState.isLoading = false;
    }
  },
  
  /**
   * Fetch a single discussion by ID
   */
  async getDiscussion(discussionId) {
    if (DiscussionState.isLoading) return;
    
    DiscussionState.isLoading = true;
    
    try {
      // Show loading UI
      DiscussionUI.showDiscussionLoading();
      
      // Check cache first
      const cacheKey = `/discussions/api/discussions/${discussionId}`;
      const cachedResponse = this.checkCache(cacheKey);
      
      if (cachedResponse) {
        console.log('Using cached data for discussion', discussionId);
        DiscussionUI.renderSingleDiscussion(cachedResponse);
        DiscussionState.isLoading = false;
        return;
      }
      
      const response = await fetch(cacheKey, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to load discussion');
      }
      
      const data = await response.json();
      
      // Cache the discussion (shorter time since it changes more)
      this.cacheResponse(cacheKey, data, 60); // 1 minute
      
      DiscussionUI.renderSingleDiscussion(data);
    } catch (error) {
      console.error('Single discussion loading error:', error);
      DiscussionUI.showError(error.message || 'Failed to load discussion');
      DiscussionUI.showSingleDiscussionError();
    } finally {
      DiscussionState.isLoading = false;
    }
  },
  
  /**
   * Create a new discussion
   */
  async createDiscussion(discussionData) {
    if (DiscussionState.isLoading) return;
    
    DiscussionState.isLoading = true;
    
    try {
      const response = await fetch('/discussions/api/discussions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCsrfToken()
        },
        body: JSON.stringify(discussionData)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Create discussion error response:', errorText);
        throw new Error(`Failed to create discussion: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Invalidate the discussions list cache
      this.invalidateCache(/\/discussions\/api\/discussions\?/);
      
      return data;
    } catch (error) {
      console.error('Create discussion error:', error);
      throw error;
    } finally {
      DiscussionState.isLoading = false;
    }
  },
  
  /**
   * Add a comment to a discussion
   */
  async addComment(discussionId, content) {
    if (DiscussionState.isLoading) return;
    
    DiscussionState.isLoading = true;
    
    try {
      const response = await fetch(`/discussions/api/discussions/${discussionId}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCsrfToken()
        },
        body: JSON.stringify({ content })
      });
      
      if (!response.ok) {
        throw new Error('Failed to post comment');
      }
      
      const data = await response.json();
      
      // Invalidate the discussion cache
      this.invalidateCache(`/discussions/api/discussions/${discussionId}`);
      
      return data;
    } catch (error) {
      console.error('Comment error:', error);
      throw error;
    } finally {
      DiscussionState.isLoading = false;
    }
  },
  
  /**
   * Vote on a discussion or comment
   */
  async vote(id, type, voteType) {
    if (!DiscussionState.userId) {
      DiscussionUI.showError('You must be logged in to vote');
      return;
    }
    
    const url = type === 'discussion' 
      ? `/discussions/api/discussions/${id}/vote`
      : `/discussions/api/comments/${id}/vote`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCsrfToken()
        },
        body: JSON.stringify({ vote_type: voteType })
      });
      
      if (!response.ok) {
        throw new Error('Failed to register vote');
      }
      
      const data = await response.json();
      
      // Invalidate cache for the affected discussion
      if (type === 'discussion') {
        this.invalidateCache(`/discussions/api/discussions/${id}`);
      } else {
        // For comments, invalidate the parent discussion
        this.invalidateCache(`/discussions/api/discussions/${DiscussionState.currentDiscussionId}`);
      }
      
      return data;
    } catch (error) {
      console.error('Vote error:', error);
      DiscussionUI.showError(error.message || 'Failed to vote');
      throw error;
    }
  },
  
  /**
   * Cache management functions
   */
  checkCache(key) {
    try {
      const cachedItem = localStorage.getItem(`disc_cache_${key}`);
      if (!cachedItem) return null;
      
      const { data, expiry } = JSON.parse(cachedItem);
      
      // Check if expired
      if (expiry < Date.now()) {
        localStorage.removeItem(`disc_cache_${key}`);
        return null;
      }
      
      return data;
    } catch (e) {
      console.warn('Cache read error:', e);
      return null;
    }
  },
  
  cacheResponse(key, data, seconds = 300) {
    try {
      const cacheItem = {
        data,
        expiry: Date.now() + (seconds * 1000)
      };
      
      localStorage.setItem(`disc_cache_${key}`, JSON.stringify(cacheItem));
    } catch (e) {
      console.warn('Cache write error:', e);
    }
  },
  
  invalidateCache(keyPattern) {
    try {
      // If keyPattern is a string, convert to RegExp
      const pattern = keyPattern instanceof RegExp ? keyPattern : new RegExp(keyPattern);
      
      // Find all matching cache keys
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('disc_cache_') && pattern.test(key.substring(11))) {
          localStorage.removeItem(key);
        }
      }
    } catch (e) {
      console.warn('Cache invalidation error:', e);
    }
  }
};

// Handle voting functionality
function handleVote(element, type, discussionId, commentId = null) {
    const url = commentId ?
        `/discussions/${discussionId}/comment/${commentId}/vote/${type}` :
        `/discussions/${discussionId}/vote/${type}`;
    
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    // Disable buttons during request
    const container = element.closest('.voting-buttons');
    const upvoteBtn = container.querySelector('[data-vote-type="up"]');
    const downvoteBtn = container.querySelector('[data-vote-type="down"]');
    upvoteBtn.disabled = true;
    downvoteBtn.disabled = true;

    fetch(url, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const scoreElement = container.querySelector('.score');
            
            // Update vote counts
            upvoteBtn.querySelector('.vote-count').textContent = data.upvotes || '0';
            downvoteBtn.querySelector('.vote-count').textContent = data.downvotes || '0';
            if (scoreElement) {
                scoreElement.textContent = data.score || '0';
            }

            // Get current user ID from the page
            const currentUserId = document.querySelector('meta[name="user-id"]')?.content;
            
            // Correctly toggle voted state based on the response
            if (type === 'up') {
                upvoteBtn.dataset.voted = 'true';
                downvoteBtn.dataset.voted = 'false';
            } else if (type === 'down') {
                downvoteBtn.dataset.voted = 'true';
                upvoteBtn.dataset.voted = 'false';
            }

            // Update button styles
            updateVoteButtonStyles(upvoteBtn);
            updateVoteButtonStyles(downvoteBtn);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to register vote. Please try again.');
    })
    .finally(() => {
        // Re-enable buttons
        upvoteBtn.disabled = false;
        downvoteBtn.disabled = false;
    });
}

// Update vote button styles based on voted state
function updateVoteButtonStyles(button) {
    if (button.dataset.voted === 'true') {
        button.classList.add('active');
    } else {
        button.classList.remove('active');
    }
}

// Handle comment replies
function handleReply(commentId) {
    const replyForm = document.querySelector(`form[data-parent-id="${commentId}"]`);
    replyForm.classList.toggle('d-none');
}

// Submit comment reply
function submitReply(form, discussionId) {
    const content = form.querySelector('textarea').value;
    const parentId = form.dataset.parentId;
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    // Disable submit button during request
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    fetch(`/discussions/${discussionId}/comment`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: new URLSearchParams({
            'content': content,
            'parent_id': parentId,
            'csrf_token': csrfToken
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Create and insert the new comment dynamically
            const commentData = data.comment;
            if (parentId) {
                // This is a reply to an existing comment
                const parentComment = document.getElementById(`comment-${parentId}`);
                if (parentComment) {
                    let nestedComments = parentComment.querySelector('.nested-comments');
                    if (!nestedComments) {
                        nestedComments = document.createElement('div');
                        nestedComments.className = 'nested-comments';
                        parentComment.querySelector('.flex-grow-1').appendChild(nestedComments);
                    }
                    nestedComments.innerHTML += createCommentHTML(commentData, discussionId);
                    // Hide the reply form
                    form.classList.add('d-none');
                    // Clear the textarea
                    form.querySelector('textarea').value = '';
                }
            } else {
                // This is a top-level comment
                const commentsContainer = document.querySelector('.comments-container');
                if (commentsContainer) {
                    commentsContainer.innerHTML += createCommentHTML(commentData, discussionId);
                    // Clear the textarea
                    form.querySelector('textarea').value = '';
                }
            }
            // Attach event listeners to the new comment
            attachEventListeners();
        } else {
            alert(data.error || 'Failed to post comment. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to post comment. Please try again.');
    })
    .finally(() => {
        // Re-enable submit button
        if (submitBtn) submitBtn.disabled = false;
    });
}

// Share discussion
function shareDiscussion(button) {
    const url = button.dataset.url;
    if (navigator.share) {
        navigator.share({
            title: document.title,
            url: url
        });
    } else {
        navigator.clipboard.writeText(url)
            .then(() => {
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip show';
                tooltip.textContent = 'Link copied!';
                button.appendChild(tooltip);
                setTimeout(() => tooltip.remove(), 2000);
            });
    }
}

// Create HTML for a new comment
function createCommentHTML(comment, discussionId) {
    const currentUserId = document.querySelector('meta[name="user-id"]')?.content;
    const isAuthenticated = !!currentUserId;
    const timestamp = new Date(comment.created_at).toLocaleString();
    const avatarUrl = comment.author?.avatar_url || '/static/images/default-avatar.png';
    const username = comment.username || 'Anonymous';
    
    return `
    <div class="comment" id="comment-${comment.id}">
        <div class="d-flex">
            <div class="flex-shrink-0">
                <img src="${avatarUrl}" class="rounded-circle" style="width: 32px; height: 32px; object-fit: cover;">
            </div>
            <div class="flex-grow-1 ms-3">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${username}</strong>
                        <small class="text-muted">${timestamp}</small>
                    </div>
                    <div class="voting-buttons" data-comment-id="${comment.id}" data-discussion-id="${discussionId}">
                        <button class="btn btn-sm vote-btn upvote-btn" data-vote-type="up" data-voted="${comment.votes?.up?.includes(currentUserId) ? 'true' : 'false'}">
                            <i class="fas fa-arrow-up"></i>
                            <span class="vote-count">${comment.votes?.up?.length || 0}</span>
                        </button>
                        <span class="score mx-1">${comment.score || 0}</span>
                        <button class="btn btn-sm vote-btn downvote-btn" data-vote-type="down" data-voted="${comment.votes?.down?.includes(currentUserId) ? 'true' : 'false'}">
                            <i class="fas fa-arrow-down"></i>
                            <span class="vote-count">${comment.votes?.down?.length || 0}</span>
                        </button>
                    </div>
                </div>
                <div class="comment-content my-2">
                    ${comment.content}
                </div>
                <div class="comment-actions">
                    ${isAuthenticated ? `
                    <button class="btn btn-sm btn-link reply-btn" data-comment-id="${comment.id}">
                        <i class="fas fa-reply"></i> Reply
                    </button>
                    ` : ''}
                </div>
                ${isAuthenticated ? `
                <form method="POST" action="/discussions/${discussionId}/comment" class="reply-form mt-2 d-none" data-parent-id="${comment.id}">
                    <input type="hidden" name="csrf_token" value="${document.querySelector('meta[name="csrf-token"]')?.content}">
                    <input type="hidden" name="parent_id" value="${comment.id}">
                    <textarea name="content" class="form-control" rows="2" placeholder="Write a reply..." required></textarea>
                    <div class="mt-2">
                        <button type="submit" class="btn btn-sm btn-primary">Submit</button>
                        <button type="button" class="btn btn-sm btn-link cancel-reply">Cancel</button>
                    </div>
                </form>
                ` : ''}
            </div>
        </div>
    </div>
    `;
}

// Attach event listeners to dynamically added elements
function attachEventListeners() {
    // Voting buttons
    document.querySelectorAll('.vote-btn').forEach(button => {
        // Remove existing event listeners to prevent duplicates
        button.removeEventListener('click', voteClickHandler);
        // Add new event listener
        button.addEventListener('click', voteClickHandler);
    });

    // Reply buttons
    document.querySelectorAll('.reply-btn').forEach(button => {
        // Remove existing event listeners to prevent duplicates
        button.removeEventListener('click', replyClickHandler);
        // Add new event listener
        button.addEventListener('click', replyClickHandler);
    });

    // Reply forms
    document.querySelectorAll('.reply-form').forEach(form => {
        // Remove existing event listeners to prevent duplicates
        form.removeEventListener('submit', formSubmitHandler);
        // Add new event listener
        form.addEventListener('submit', formSubmitHandler);
    });

    // Cancel reply buttons
    document.querySelectorAll('.cancel-reply').forEach(button => {
        // Remove existing event listeners to prevent duplicates
        button.removeEventListener('click', cancelReplyHandler);
        // Add new event listener
        button.addEventListener('click', cancelReplyHandler);
    });
}

// Event handler functions
function voteClickHandler() {
    const container = this.closest('.voting-buttons');
    const discussionId = container.dataset.discussionId;
    const commentId = container.dataset.commentId;
    const voteType = this.dataset.voteType;
    handleVote(this, voteType, discussionId, commentId);
}

function replyClickHandler() {
    handleReply(this.dataset.commentId);
}

function formSubmitHandler(e) {
    e.preventDefault();
    const discussionId = this.closest('.card').querySelector('.voting-buttons').dataset.discussionId;
    submitReply(this, discussionId);
}

function cancelReplyHandler() {
    this.closest('form').classList.add('d-none');
}

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Main comment form
    const mainCommentForm = document.getElementById('main-comment-form');
    if (mainCommentForm) {
        mainCommentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const discussionId = document.querySelector('.voting-buttons').dataset.discussionId;
            submitReply(this, discussionId);
        });
    }

    // Attach event listeners to all interactive elements
    attachEventListeners();

    // Share button
    const shareButton = document.getElementById('shareDiscussion');
    if (shareButton) {
        shareButton.addEventListener('click', function() {
            shareDiscussion(this);
        });
    }
});