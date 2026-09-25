/**
 * Discussion System Main Module
 * Initializes and connects all components
 */

// Additional UI methods for single discussion view
DiscussionUI.showSingleDiscussion = function(discussionId) {
  if (DiscussionState.isLoading) return;
  
  // Update state
  DiscussionState.currentDiscussionId = discussionId;
  
  // Show discussion
  DiscussionAPI.getDiscussion(discussionId);
  
  // Update URL without reloading
  window.history.pushState({id: discussionId}, '', `/discussions/${discussionId}`);
};

DiscussionUI.showDiscussionLoading = function() {
  const singleView = document.getElementById('singleDiscussionView');
  if (!singleView) return;
  
  // Show single view, hide list
  document.getElementById('discussionsList')?.classList.add('d-none');
  singleView.classList.remove('d-none');
  document.getElementById('pagination')?.classList.add('d-none');
  
  singleView.innerHTML = `
    <div class="mb-4">
      <button class="btn btn-outline-secondary mb-4 disabled">
        <i class="fas fa-arrow-left me-2"></i> Back to Discussions
      </button>
      
      <div class="card shadow-sm mb-4">
        <div class="card-body p-4">
          <div class="d-flex align-items-center mb-3">
            <div class="d-flex align-items-center">
              <div class="skeleton" style="width: 40px; height: 40px; border-radius: 50%;"></div>
              <div class="ms-3">
                <div class="skeleton" style="width: 120px; height: 1rem;"></div>
                <div class="skeleton mt-1" style="width: 80px; height: 0.8rem;"></div>
              </div>
            </div>
          </div>
          
          <div class="skeleton skeleton-title" style="height: 2rem; width: 70%;"></div>
          <div class="mt-4">
            <div class="skeleton skeleton-text"></div>
            <div class="skeleton skeleton-text"></div>
            <div class="skeleton skeleton-text"></div>
            <div class="skeleton skeleton-text"></div>
          </div>
        </div>
      </div>
      
      <div class="card shadow-sm">
        <div class="card-header bg-white">
          <div class="skeleton" style="width: 120px; height: 1.5rem;"></div>
        </div>
        <div class="card-body p-4">
          <div class="skeleton" style="height: 100px;"></div>
        </div>
      </div>
    </div>
  `;
};

DiscussionUI.showSingleDiscussionError = function() {
  const singleView = document.getElementById('singleDiscussionView');
  if (!singleView) return;
  
  // Show single view, hide list
  document.getElementById('discussionsList')?.classList.add('d-none');
  singleView.classList.remove('d-none');
  document.getElementById('pagination')?.classList.add('d-none');
  
  singleView.innerHTML = `
    <div class="card shadow-sm bg-light p-5 text-center">
      <div class="mb-4">
        <i class="fas fa-exclamation-circle text-danger fa-3x"></i>
      </div>
      <h3 class="h4 mb-3">Failed to load discussion</h3>
      <p class="text-secondary mb-4">The discussion could not be loaded or does not exist.</p>
      <button id="backButtonError" class="btn btn-primary">
        <i class="fas fa-arrow-left me-2"></i> Back to Discussions
      </button>
    </div>
  `;
  
  document.getElementById('backButtonError')?.addEventListener('click', (e) => {
    e.preventDefault();
    window.history.pushState({}, '', '/discussions/');
    document.getElementById('discussionsList')?.classList.remove('d-none');
    document.getElementById('singleDiscussionView')?.classList.add('d-none');
    document.getElementById('pagination')?.classList.remove('d-none');
    DiscussionState.currentDiscussionId = '';
    DiscussionAPI.getDiscussions();
  });
};

DiscussionUI.renderSingleDiscussion = function(discussion) {
  const singleView = document.getElementById('singleDiscussionView');
  if (!singleView) return;
  
  // Show single view, hide list
  document.getElementById('discussionsList')?.classList.add('d-none');
  singleView.classList.remove('d-none');
  document.getElementById('pagination')?.classList.add('d-none');
  
  const userInitial = discussion.username ? discussion.username.charAt(0).toUpperCase() : 'A';
  const hasVoted = DiscussionState.userId ? 
                  (discussion.votes?.up?.includes(DiscussionState.userId) ? 'up' : 
                   discussion.votes?.down?.includes(DiscussionState.userId) ? 'down' : null) : null;
  
  singleView.innerHTML = `
    <div class="mb-4">
      <button id="backButton" class="btn btn-outline-secondary mb-4">
        <i class="fas fa-arrow-left me-2"></i> Back to Discussions
      </button>
      
      <div class="card shadow-sm mb-4">
        <div class="card-body p-4">
          <!-- Content Header -->
          <div class="d-flex align-items-center mb-3">
            <div class="d-flex align-items-center">
              <div class="bg-secondary text-white rounded-circle d-flex align-items-center justify-content-center fs-5 fw-medium me-3" style="width: 40px; height: 40px;">
                ${userInitial}
              </div>
              <div>
                <p class="mb-0 fw-medium">${this.escapeHtml(discussion.username || 'Anonymous')}</p>
                <p class="text-muted mb-0 small">${this.formatDate(discussion.created_at)}</p>
              </div>
            </div>
            
            <div class="ms-auto d-flex align-items-center gap-3 text-muted small">
              ${discussion.subject && discussion.subject !== 'General' ? 
                `<span class="badge bg-primary-subtle text-primary">
                  ${this.escapeHtml(discussion.subject)}
                </span>` : ''}
                
              ${discussion.grade_level && discussion.grade_level !== 'General' ? 
                `<span class="badge bg-info-subtle text-info">
                  ${this.escapeHtml(discussion.grade_level)}
                </span>` : ''}
                
              <span class="d-flex align-items-center gap-1">
                <i class="fas fa-eye"></i>
                ${discussion.views || 0} views
              </span>
            </div>
          </div>
            
          <!-- Content -->
          <h1 class="h3 fw-bold mb-4">${this.escapeHtml(discussion.title)}</h1>
          <div class="mb-4 discussion-content">
            ${this.escapeHtml(discussion.content).replace(/\n/g, '<br>')}
          </div>
            
          <!-- Vote Controls -->
          <div class="d-flex align-items-center mt-4 pb-3 border-bottom">
            <div class="d-flex align-items-center gap-1">
              <button class="vote-btn upvote btn btn-sm btn-light rounded-circle ${hasVoted === 'up' ? 'text-primary' : ''}" 
                     data-id="${discussion.id}" data-type="discussion">
                <i class="fas fa-chevron-up"></i>
              </button>
              <span class="score fw-medium mx-2">${discussion.score || 0}</span>
              <button class="vote-btn downvote btn btn-sm btn-light rounded-circle ${hasVoted === 'down' ? 'text-danger' : ''}" 
                     data-id="${discussion.id}" data-type="discussion">
                <i class="fas fa-chevron-down"></i>
              </button>
            </div>
            
            <div class="ms-auto">
              <button class="btn btn-sm btn-outline-primary share-btn" data-id="${discussion.id}">
                <i class="fas fa-share-alt me-1"></i> Share
              </button>
            </div>
          </div>
        </div>
      </div>
        
      <!-- Comments Section -->
      <div class="card shadow-sm">
        <div class="card-header bg-white">
          <h5 class="mb-0">Comments (${discussion.comments?.length || 0})</h5>
        </div>
        <div class="card-body p-4">
          <!-- Comment Form -->
          <form id="commentForm" class="mb-4">
            <div class="mb-3">
              <label for="commentContent" class="form-label">Add a comment</label>
              <textarea id="commentContent" class="form-control" rows="3" placeholder="Share your thoughts..."></textarea>
            </div>
            <div class="text-end">
              <button type="submit" class="btn btn-primary">Post Comment</button>
            </div>
          </form>
          
          <!-- Comments List -->
          <div id="commentsList" class="border-top pt-4 mt-2">
            ${this.renderComments(discussion.comments)}
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Add event listeners
  
  // Back button
  document.getElementById('backButton')?.addEventListener('click', (e) => {
    e.preventDefault();
    window.history.pushState({}, '', '/discussions/');
    document.getElementById('discussionsList')?.classList.remove('d-none');
    document.getElementById('singleDiscussionView')?.classList.add('d-none');
    document.getElementById('pagination')?.classList.remove('d-none');
    DiscussionState.currentDiscussionId = '';
    DiscussionAPI.getDiscussions();
  });
  
  // Comment form
  this.setupCommentForm(discussion.id);
  
  // Vote buttons
  singleView.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', this.handleVote.bind(this));
  });
  
  // Share button
  singleView.querySelector('.share-btn')?.addEventListener('click', this.handleShare.bind(this));
};

DiscussionUI.renderComments = function(comments) {
  if (!comments || comments.length === 0) {
    return `
      <div class="text-center py-4">
        <i class="fas fa-comments text-secondary fa-2x mb-3"></i>
        <p class="text-secondary">No comments yet. Be the first to comment!</p>
      </div>
    `;
  }
  
  return comments
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .map(comment => {
      const userInitial = comment.username ? comment.username.charAt(0).toUpperCase() : 'A';
      const hasVoted = DiscussionState.userId ? 
                       (comment.votes?.up?.includes(DiscussionState.userId) ? 'up' : 
                        comment.votes?.down?.includes(DiscussionState.userId) ? 'down' : null) : null;
      
      return `
        <div class="mb-4 comment" id="comment-${comment.id}">
          <div class="d-flex gap-3">
            <div class="bg-light text-secondary rounded-circle d-flex align-items-center justify-content-center fs-6 fw-medium" style="width: 32px; height: 32px; flex-shrink: 0;">
              ${userInitial}
            </div>
            <div class="flex-grow-1">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <div>
                  <span class="fw-medium">${this.escapeHtml(comment.username || 'Anonymous')}</span>
                  <span class="text-muted ms-2 small">${this.formatDate(comment.created_at)}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <button class="vote-btn upvote btn btn-sm btn-light rounded-circle ${hasVoted === 'up' ? 'text-primary' : 'text-secondary'}" data-id="${comment.id}" data-type="comment">
                    <i class="fas fa-chevron-up"></i>
                  </button>
                  <span class="score small fw-medium">${comment.score || 0}</span>
                  <button class="vote-btn downvote btn btn-sm btn-light rounded-circle ${hasVoted === 'down' ? 'text-danger' : 'text-secondary'}" data-id="${comment.id}" data-type="comment">
                    <i class="fas fa-chevron-down"></i>
                  </button>
                </div>
              </div>
              <div>${this.escapeHtml(comment.content).replace(/\n/g, '<br>')}</div>
            </div>
          </div>
        </div>
      `;
    })
    .join('');
};

DiscussionUI.handleShare = function(e) {
  const discussionId = e.currentTarget.dataset.id;
  const shareUrl = `${window.location.origin}/discussions/${discussionId}`;
  
  if (navigator.share) {
    navigator.share({
      title: 'Shared Discussion',
      url: shareUrl
    }).catch(err => {
      console.error('Share error:', err);
      this.handleCopyToClipboard(shareUrl);
    });
  } else {
    this.handleCopyToClipboard(shareUrl);
  }
};

DiscussionUI.handleCopyToClipboard = function(text) {
  navigator.clipboard.writeText(text)
    .then(() => {
      this.showSuccess('Link copied to clipboard');
    })
    .catch(err => {
      console.error('Clipboard error:', err);
      this.showError('Failed to copy link');
    });
};

DiscussionUI.setupCommentForm = function(discussionId) {
  const commentForm = document.getElementById('commentForm');
  if (!commentForm) return;
  
  commentForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const content = document.getElementById('commentContent')?.value.trim();
    
    if (!content) {
      this.showError('Comment cannot be empty');
      return;
    }
    
    if (!DiscussionState.userId) {
      this.showError('You must be logged in to comment');
      return;
    }
    
    try {
      // Disable form
      this.setFormDisabled(commentForm, true);
      
      await DiscussionAPI.addComment(discussionId, content);
      
      // Clear form
      if (document.getElementById('commentContent')) {
        document.getElementById('commentContent').value = '';
      }
      
      // Show success message
      this.showSuccess('Comment posted successfully');
      
      // Reload discussion to show new comment
      DiscussionAPI.getDiscussion(discussionId);
    } catch (error) {
      this.showError(error.message || 'Failed to post comment');
    } finally {
      this.setFormDisabled(commentForm, false);
    }
  });
};

DiscussionUI.handleVote = function(e) {
  e.preventDefault();
  e.stopPropagation();
  
  const btn = e.currentTarget;
  const id = btn.getAttribute('data-id');
  const type = btn.getAttribute('data-type');
  const voteType = btn.classList.contains('upvote') ? 'up' : 'down';
  
  if (!DiscussionState.userId) {
    this.showError('You must be logged in to vote');
    return;
  }
  
  DiscussionAPI.vote(id, type, voteType)
    .then(data => {
      // Update score display
      const scoreElement = btn.parentElement.querySelector('.score');
      if (scoreElement) {
        scoreElement.textContent = data.score || 0;
      }
      
      // Update button styles
      const upvoteBtn = btn.parentElement.querySelector('.upvote');
      const downvoteBtn = btn.parentElement.querySelector('.downvote');
      
      if (voteType === 'up') {
        if (data.voted === 'up') {
          upvoteBtn.classList.add('text-primary');
          upvoteBtn.classList.remove('text-secondary');
          downvoteBtn.classList.add('text-secondary');
          downvoteBtn.classList.remove('text-danger');
        } else {
          upvoteBtn.classList.remove('text-primary');
          upvoteBtn.classList.add('text-secondary');
        }
      } else {
        if (data.voted === 'down') {
          downvoteBtn.classList.add('text-danger');
          downvoteBtn.classList.remove('text-secondary');
          upvoteBtn.classList.add('text-secondary');
          upvoteBtn.classList.remove('text-primary');
        } else {
          downvoteBtn.classList.remove('text-danger');
          downvoteBtn.classList.add('text-secondary');
        }
      }
    })
    .catch(error => {
      console.error('Vote error:', error);
    });
};

DiscussionUI.updatePagination = function(data) {
  const paginationElement = document.getElementById('pagination');
  if (!paginationElement) return;
  
  const totalPages = Math.ceil(data.total / data.per_page);
  
  if (totalPages <= 1) {
    paginationElement.classList.add('d-none');
    return;
  }
  
  paginationElement.classList.remove('d-none');
  
  // Create pagination nav
  const paginationNav = document.createElement('nav');
  paginationNav.setAttribute('aria-label', 'Discussions pagination');
  
  const paginationUl = document.createElement('ul');
  paginationUl.className = 'pagination';
  
  // Previous button
  const prevLi = document.createElement('li');
  prevLi.className = `page-item ${DiscussionState.currentPage === 1 ? 'disabled' : ''}`;
  
  const prevLink = document.createElement('a');
  prevLink.className = 'page-link';
  prevLink.href = '#';
  prevLink.textContent = 'Previous';
  if (DiscussionState.currentPage > 1) {
    prevLink.addEventListener('click', (e) => {
      e.preventDefault();
      DiscussionState.currentPage--;
      DiscussionAPI.getDiscussions();
    });
  }
  prevLi.appendChild(prevLink);
  paginationUl.appendChild(prevLi);
  
  // Page buttons
  const startPage = Math.max(1, DiscussionState.currentPage - 2);
  const endPage = Math.min(totalPages, DiscussionState.currentPage + 2);
  
  // Show first page if not included in range
  if (startPage > 1) {
    paginationUl.appendChild(this.createPageButton(1));
    
    // Add ellipsis if there's a gap
    if (startPage > 2) {
      paginationUl.appendChild(this.createEllipsis());
    }
  }
  
  // Generate page numbers
  for (let i = startPage; i <= endPage; i++) {
    paginationUl.appendChild(this.createPageButton(i, i === DiscussionState.currentPage));
  }
  
  // Show last page if not included in range
  if (endPage < totalPages) {
    // Add ellipsis if there's a gap
    if (endPage < totalPages - 1) {
      paginationUl.appendChild(this.createEllipsis());
    }
    
    paginationUl.appendChild(this.createPageButton(totalPages));
  }
  
  // Next button
  const nextLi = document.createElement('li');
  nextLi.className = `page-item ${DiscussionState.currentPage === totalPages ? 'disabled' : ''}`;
  
  const nextLink = document.createElement('a');
  nextLink.className = 'page-link';
  nextLink.href = '#';
  nextLink.textContent = 'Next';
  if (DiscussionState.currentPage < totalPages) {
    nextLink.addEventListener('click', (e) => {
      e.preventDefault();
      DiscussionState.currentPage++;
      DiscussionAPI.getDiscussions();
    });
  }
  nextLi.appendChild(nextLink);
  paginationUl.appendChild(nextLi);
  
  paginationNav.appendChild(paginationUl);
  
  // Clear previous pagination
  paginationElement.innerHTML = '';
  paginationElement.appendChild(paginationNav);
  
  // Add invisible element for intersection observer
  if (DiscussionState.currentPage < totalPages) {
    const triggerElement = document.createElement('div');
    triggerElement.id = 'paginationTrigger';
    triggerElement.style.height = '1px';
    triggerElement.dataset.hasMore = 'true';
    paginationElement.appendChild(triggerElement);
    
    // Observe it for lazy loading
    if (this.observers && this.observers.pagination) {
      this.observers.pagination.observe(triggerElement);
    }
  }
};

DiscussionUI.createPageButton = function(pageNum, isActive = false) {
  const pageLi = document.createElement('li');
  pageLi.className = `page-item ${isActive ? 'active' : ''}`;
  
  const pageLink = document.createElement('a');
  pageLink.className = 'page-link';
  pageLink.href = '#';
  pageLink.textContent = pageNum;
  
  if (!isActive) {
    pageLink.addEventListener('click', (e) => {
      e.preventDefault();
      DiscussionState.currentPage = pageNum;
      DiscussionAPI.getDiscussions();
    });
  }
  
  pageLi.appendChild(pageLink);
  return pageLi;
};

DiscussionUI.createEllipsis = function() {
  const ellipsisLi = document.createElement('li');
  ellipsisLi.className = 'page-item disabled';
  
  const ellipsisSpan = document.createElement('span');
  ellipsisSpan.className = 'page-link';
  ellipsisSpan.textContent = '...';
  
  ellipsisLi.appendChild(ellipsisSpan);
  return ellipsisLi;
};

DiscussionUI.handleNavigation = function(e) {
  if (e.state && e.state.id) {
    // Show the discussion from state
    this.showSingleDiscussion(e.state.id);
  } else {
    // Return to discussions list
    document.getElementById('discussionsList')?.classList.remove('d-none');
    document.getElementById('singleDiscussionView')?.classList.add('d-none');
    document.getElementById('pagination')?.classList.remove('d-none');
    DiscussionState.currentDiscussionId = '';
    DiscussionAPI.getDiscussions();
  }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
  // Initialize state
  DiscussionState.init();
  
  // Initialize UI
  DiscussionUI.init();
  
  // Register service worker for better performance and offline capability
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/js/discussion-sw.js')
      .then(registration => {
        console.log('Service Worker registered with scope:', registration.scope);
      })
      .catch(error => {
        console.error('Service Worker registration failed:', error);
      });
  }
}); 