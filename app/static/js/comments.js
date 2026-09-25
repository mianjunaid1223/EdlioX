/**
 * Comments API JavaScript Module
 * Handles all comment-related functionality on the frontend
 */

// Keep track of the CSRF token and current user ID
let csrf_token = null;
let currentUserId = null;

// Initialize comments system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing comments system');
    
    // Check if we're on a resource page
    const resourceContainer = document.getElementById('resource-comments');
    console.log('Resource container found:', resourceContainer);
    
    if (resourceContainer) {
        // Get the resource ID
        const resourceId = resourceContainer.dataset.resourceId;
        console.log('Resource ID from data attribute:', resourceId);
        
        // Get CSRF token
        csrf_token = getCsrfToken();
        console.log('CSRF token obtained:', csrf_token ? 'Yes' : 'No');
        
        // Get current user ID
        currentUserId = document.body.dataset.userId || null;
        console.log('Current user ID:', currentUserId);
        
        if (resourceId) {
            // Use the new initialization function
            console.log('Calling initializeComments with resourceId:', resourceId);
            initializeComments(csrf_token, currentUserId);
        } else {
            console.error('No resource ID found in data-resource-id attribute');
        }
    } else {
        console.log('Not on a resource page with comments');
    }
    
    // Initialize button animation styles
    addButtonAnimationStyles();
});

/**
 * Load all comments for a resource
 * @param {string} resourceId - The ID of the resource
 */
function loadComments(resourceId) {
    const commentsContainer = document.getElementById('comments-list');
    if (!commentsContainer) {
        console.error('Comments container not found');
        return;
    }
    
    // Show loading indicator
    commentsContainer.innerHTML = '<div class="my-3 text-center"><i class="fas fa-spinner fa-spin"></i> Loading comments...</div>';
    
    // Fetch comments from the server
    fetch(`/api/comments/resource/${resourceId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Loaded comments:', data);
            
            if (!data.success) {
                commentsContainer.innerHTML = `<div class="alert alert-danger">${data.message || 'Failed to load comments'}</div>`;
                return;
            }
            
            const comments = data.comments;
            
            // Clear the container
            commentsContainer.innerHTML = '';
            
            if (comments.length === 0) {
                commentsContainer.innerHTML = '<div class="text-center my-3">No comments yet. Be the first to comment!</div>';
                return;
            }
            
            // Sort comments by likes count
            comments.sort((a, b) => b.likes_count - a.likes_count);
            
            // Add each comment
            comments.forEach(comment => {
                const commentElement = createCommentElement(comment);
                commentsContainer.appendChild(commentElement);
                
                // Create replies container
                const repliesDiv = document.createElement('div');
                repliesDiv.id = `replies-${comment.id}`;
                repliesDiv.className = 'ms-4 mt-2';
                
                // Check if there are replies and add them
                if (comment.replies && comment.replies.length > 0) {
                    // Sort replies by likes count (this is actually now redundant since backend already sorts them)
                    // But we'll keep it for safety in case the backend logic changes
                    comment.replies.sort((a, b) => b.likes_count - a.likes_count);
                    
                    // Add each reply
                    comment.replies.forEach(reply => {
                        const replyElement = createReplyElement(reply);
                        repliesDiv.appendChild(replyElement);
                    });
                }
                
                // Add the replies toggle button
                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'btn btn-sm btn-link toggle-replies-btn';
                toggleBtn.dataset.commentId = comment.id;
                
              
                // Create a container for replies with toggle functionality
                const repliesContainer = document.createElement('div');
                repliesContainer.id = `replies-container-${comment.id}`;
                repliesContainer.style.display = 'none';
                repliesContainer.appendChild(repliesDiv);
                
                // Append all to the comment element
                const cardBody = commentElement.querySelector('.card-body');
                cardBody.appendChild(toggleBtn);
                cardBody.appendChild(repliesContainer);
            });
        })
        .catch(error => {
            console.error('Error loading comments:', error);
            commentsContainer.innerHTML = `<div class="alert alert-danger">Failed to load comments: ${error.message}</div>`;
        });
}

/**
 * Initialize comments section
 * @param {string} csrfToken - The CSRF token
 * @param {string} userId - The ID of the current user
 */
function initializeComments(csrfToken, userId) {
    console.log('initializeComments called with userId:', userId);
    csrf_token = csrfToken;
    currentUserId = userId;
    
    // Load comments for the current resource
    const resourceContainer = document.getElementById('resource-comments');
    console.log('Resource container found in init function:', resourceContainer);
    
    if (resourceContainer) {
        const resourceId = resourceContainer.dataset.resourceId;
        console.log('Resource ID in init function:', resourceId);
        
        if (resourceId) {
            console.log('Calling loadComments with resourceId:', resourceId);
            loadComments(resourceId);
            
            // Setup comment form submission - only attach this once
            const commentForm = document.getElementById('comment-form');
            if (commentForm) {
                commentForm.removeEventListener('submit', handleCommentSubmit);
                commentForm.addEventListener('submit', handleCommentSubmit);
            }
        } else {
            console.error('Resource container exists but no resource ID found');
        }
    } else {
        console.error('Resource container not found when trying to load comments');
    }
    
    // Delegate event handling to the document for dynamically added elements
    // Remove any existing handlers first to prevent duplication
    document.removeEventListener('click', handleCommentEvents);
    document.addEventListener('click', handleCommentEvents);
    
    // Setup form submission for replies - use event delegation to avoid duplicates
    document.removeEventListener('submit', handleReplyFormSubmit);
    document.addEventListener('submit', handleReplyFormSubmit);
}

// Handler for comment form submission
function handleCommentSubmit(e) {
    e.preventDefault();
    const resourceContainer = document.getElementById('resource-comments');
    const resourceId = resourceContainer.dataset.resourceId;
    submitComment(resourceId);
}

// Handler for reply form submissions
function handleReplyFormSubmit(event) {
    if (event.target.closest('.reply-form-inner')) {
        event.preventDefault();
        const form = event.target.closest('.reply-form-inner');
        const commentId = form.querySelector('[name="comment_id"]').value;
        submitReply(commentId, form);
    }
}

// Handler for all comment-related click events
function handleCommentEvents(event) {
    // Like/dislike buttons
    if (event.target.closest('.like-btn')) {
        const button = event.target.closest('.like-btn');
        // Check if this is a comment or reply like button
        if (button.dataset.commentId) {
            const commentId = button.dataset.commentId;
            const type = button.dataset.type;
            likeItem(commentId, type, button);
        } else if (button.dataset.replyId) {
            const replyId = button.dataset.replyId;
            likeReply(replyId);
        }
    }
    else if (event.target.closest('.dislike-btn')) {
        const button = event.target.closest('.dislike-btn');
        // Check if this is a comment or reply dislike button
        if (button.dataset.commentId) {
            const commentId = button.dataset.commentId;
            const type = button.dataset.type;
            dislikeItem(commentId, type, button);
        } else if (button.dataset.replyId) {
            const replyId = button.dataset.replyId;
            dislikeReply(replyId);
        }
    }
    // Reply button - show the reply form
    else if (event.target.closest('.reply-btn')) {
        const button = event.target.closest('.reply-btn');
        const commentId = button.dataset.commentId;
        const replyForm = document.getElementById(`reply-form-${commentId}`);
        if (replyForm) {
            replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
        }
    }
    // Cancel reply button
    else if (event.target.closest('.cancel-reply')) {
        const button = event.target.closest('.cancel-reply');
        const replyForm = button.closest('.reply-form');
        if (replyForm) {
            replyForm.style.display = 'none';
        }
    }
    // Toggle replies visibility
    else if (event.target.closest('.toggle-replies-btn')) {
        const button = event.target.closest('.toggle-replies-btn');
        const commentId = button.dataset.commentId;
        console.log('Toggle replies clicked for comment:', commentId);
        
        const repliesContainer = document.getElementById(`replies-container-${commentId}`);
        if (repliesContainer) {
            console.log('Found replies container:', repliesContainer.id);
            const isHidden = repliesContainer.style.display === 'none';
            repliesContainer.style.display = isHidden ? 'block' : 'none';
            console.log('Toggled display to:', repliesContainer.style.display);
            
            // Count replies
            const repliesDiv = document.getElementById(`replies-${commentId}`);
            const replyCount = repliesDiv ? repliesDiv.querySelectorAll('.reply-card').length : 0;
            const replyText = replyCount === 1 ? '1 reply' : `${replyCount} replies`;
            
            // Update button text
            button.innerHTML = isHidden ? 
                `<i class="fas fa-comments"></i> Hide ${replyText}` : 
                `<i class="fas fa-comments"></i> ${replyText}`;
        } else {
            console.error('Could not find replies container for comment:', commentId);
        }
    }
}

/**
 * Create a DOM element for a comment
 * @param {Object} comment - Comment data
 * @returns {HTMLElement} - The comment DOM element
 */
function createCommentElement(comment) {
    const commentDiv = document.createElement('div');
    commentDiv.className = 'card shadow-sm mb-3 comment-card';
    commentDiv.id = `comment-${comment.id}`;
    
    // Format date
    const date = new Date(comment.created_at);
    const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    
    // Determine if user has liked or disliked
    const userLiked = comment.user_liked === true;
    const userDisliked = comment.user_disliked === true;
    
    // Count replies
    const replyCount = comment.replies ? comment.replies.length : 0;
    const replyText = replyCount === 1 ? '1 reply' : `${replyCount} replies`;
    
    // Get avatar URL or default
    const avatarUrl = comment.author && comment.author.avatar_url ? 
        comment.author.avatar_url : '/static/images/default-avatar.png';
    
    // Get username or default
    const username = comment.author && comment.author.username ? 
        escapeHtml(comment.author.username) : 'Anonymous';
    
    // Set inner HTML
    commentDiv.innerHTML = `
        <div class="card-body pb-0">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="d-flex align-items-center">
                    <a href="/profile?username=${username}" class="me-2">
                        <img src="${avatarUrl}" alt="${username}" 
                             class="rounded-circle" 
                             style="width: 40px; height: 40px; object-fit: cover;">
                    </a>
                    <div class="fw-bold">
                        <a href="/profile?username=${username}" class="text-decoration-none">
                            ${username}
                        </a>
                    </div>
                </div>
                <div class="text-muted small">${formattedDate}</div>
            </div>
            <p class="mb-3" style="white-space: pre-wrap; line-break: anywhere; text-wrap: balance;">${escapeHtml(comment.content)}</p>
            <div class="d-flex gap-2 mb-3">
                <button class="btn btn-sm ${userLiked ? 'btn-primary active' : 'btn-outline-primary'} like-btn" 
                        data-comment-id="${comment.id}" data-type="comment" aria-label="Like">
                    <i class="fas fa-thumbs-up"></i> <span class="likes-count">${comment.likes_count || 0}</span>
                </button>
                <button class="btn btn-sm ${userDisliked ? 'btn-danger active' : 'btn-outline-danger'} dislike-btn" 
                        data-comment-id="${comment.id}" data-type="comment" aria-label="Dislike">
                    <i class="fas fa-thumbs-down"></i> <span class="dislikes-count">${comment.dislikes_count || 0}</span>
                </button>
                <button class="btn btn-sm btn-outline-secondary reply-btn" data-comment-id="${comment.id}">
                    <i class="fas fa-reply"></i> Reply
                </button>
                <button class="btn btn-sm btn-outline-info toggle-replies-btn" data-comment-id="${comment.id}">
                    <i class="fas fa-comments"></i> ${replyText}
                </button>
            </div>
            
            <!-- Reply form - hidden by default -->
            <div id="reply-form-${comment.id}" class="reply-form mb-3" style="display: none;">
                <form class="reply-form-inner">
                    <input type="hidden" name="comment_id" value="${comment.id}">
                    <input type="hidden" name="csrf_token" value="${window.csrfToken || ''}">
                    <div class="form-group mb-2">
                        <textarea name="content" class="form-control" rows="2" placeholder="Write a reply..." required></textarea>
                    </div>
                    <div class="d-flex justify-content-end gap-2">
                        <button type="button" class="btn btn-sm btn-secondary cancel-reply">Cancel</button>
                        <button type="submit" class="btn btn-sm btn-primary">Post Reply</button>
                    </div>
                </form>
            </div>
            
            <!-- Replies container -->
            <div id="replies-container-${comment.id}" style="display: none;">
                <div id="replies-${comment.id}" class="replies ps-4 border-start ms-4 mb-3">
                    ${comment.replies && Array.isArray(comment.replies) ? 
                        comment.replies.map(reply => createReplyElement(reply).outerHTML).join('') 
                        : ''}
                </div>
            </div>
        </div>
    `;
    
    return commentDiv;
}

/**
 * Create a DOM element for a reply
 * @param {Object} reply - Reply data
 * @returns {HTMLElement} - The reply DOM element
 */
function createReplyElement(reply) {
    const replyDiv = document.createElement('div');
    replyDiv.className = 'card my-2 bg-light border-0 shadow-sm reply-card';
    replyDiv.id = `reply-${reply.id || (reply._id ? reply._id.toString() : 'unknown')}`;
    
    // Format date
    const date = new Date(reply.created_at);
    const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    
    // Get username and avatar or defaults
    const username = reply.author && reply.author.username ? 
        escapeHtml(reply.author.username) : 'Anonymous';
    
    const avatarUrl = reply.author && reply.author.avatar_url ? 
        reply.author.avatar_url : '/static/images/default-avatar.png';
    
    // Set the reply content
    replyDiv.innerHTML = `
        <div class="card-body py-2 px-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="d-flex align-items-center">
                    <a href="/profile?username=${username}" class="me-2">
                        <img src="${avatarUrl}" alt="${username}" 
                             class="rounded-circle" 
                             style="width: 30px; height: 30px; object-fit: cover;">
                    </a>
                    <div class="fw-bold text-sm">
                        <a href="/profile?username=${username}" class="text-decoration-none">
                            ${username}
                        </a>
                    </div>
                </div>
                <div class="text-muted small">${formattedDate}</div>
            </div>
            <div class="my-2" style="white-space: pre-wrap; line-break: anywhere; text-wrap: balance;">${escapeHtml(reply.content)}</div>
            <div class="d-flex gap-2">
                <button class="btn btn-xs ${reply.user_liked ? 'btn-primary active' : 'btn-outline-primary'} like-btn" 
                        data-reply-id="${reply.id || (reply._id ? reply._id.toString() : 'unknown')}" data-type="reply" aria-label="Like">
                    <i class="fas fa-thumbs-up"></i> <span class="likes-count">${reply.likes_count || 0}</span>
                </button>
                <button class="btn btn-xs ${reply.user_disliked ? 'btn-danger active' : 'btn-outline-danger'} dislike-btn" 
                        data-reply-id="${reply.id || (reply._id ? reply._id.toString() : 'unknown')}" data-type="reply" aria-label="Dislike">
                    <i class="fas fa-thumbs-down"></i> <span class="dislikes-count">${reply.dislikes_count || 0}</span>
                </button>
            </div>
        </div>
    `;
    
    return replyDiv;
}

/**
 * Submit a new comment
 * @param {string} resourceId - The ID of the resource
 */
function submitComment(resourceId) {
    const commentForm = document.getElementById('comment-form');
    if (!commentForm) {
        console.error('Comment form not found');
        return;
    }
    
    // Get the content
    const contentField = commentForm.querySelector('[name="content"]');
    if (!contentField) {
        console.error('Content field not found in comment form');
        return;
    }
    
    const content = contentField.value.trim();
    if (!content) {
        showAlert('Please enter a comment', 'error');
        return;
    }
    
    // Show loading state
    const submitBtn = commentForm.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Posting...';
    }
    
    // Get the CSRF token
    const csrfTokenField = commentForm.querySelector('[name="csrf_token"]');
    if (!csrfTokenField) {
        console.error('CSRF token field not found in comment form');
        showAlert('CSRF token missing. Please refresh the page.', 'error');
        return;
    }
    
    // Create form data
    const formData = new FormData();
    formData.append('content', content);
    formData.append('csrf_token', csrfTokenField.value);
    
    console.log(`Submitting comment to resource: ${resourceId}`);
    console.log(`Comment content: ${content}`);
    
    // Send the request
    fetch(`/api/comments/resource/${resourceId}`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Comment submission response:', data);
        
        // Reset form state
        contentField.value = '';
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Post Comment';
        }
        
        if (data.success) {
            // Show success message
            showAlert('Comment posted successfully!', 'success');
            
            // Add the new comment to the DOM
            if (data.comment) {
                const commentsContainer = document.getElementById('comments-list');
                if (commentsContainer) {
                    // Create the comment element
                    const commentEl = createCommentElement(data.comment);
                    
                    // If there's a "no comments yet" message, remove it
                    const noCommentsMsg = commentsContainer.querySelector('p.text-center.my-4');
                    if (noCommentsMsg && noCommentsMsg.textContent.includes('No comments yet')) {
                        commentsContainer.innerHTML = '';
                    }
                    
                    // Insert at the top
                    if (commentsContainer.firstChild) {
                        commentsContainer.insertBefore(commentEl, commentsContainer.firstChild);
                    } else {
                        commentsContainer.appendChild(commentEl);
                    }
                    
                    // Scroll to the new comment
                    commentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    // Highlight the new comment
                    commentEl.classList.add('comment-highlight');
                    setTimeout(() => {
                        commentEl.classList.remove('comment-highlight');
                    }, 3000);
                }
            } else {
                // If we didn't get the comment back, reload all comments
                loadComments(resourceId);
            }
        } else {
            showAlert(data.message || 'Error posting comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error submitting comment:', error);
        showAlert('Failed to post comment. Please try again.', 'error');
        
        // Reset button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Post Comment';
        }
    });
}

/**
 * Submit a new reply to a comment
 * @param {string} commentId - The ID of the parent comment
 * @param {HTMLFormElement} form - The reply form element
 */
function submitReply(commentId, form) {
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Posting...';
    }
    
    // Get form data
    const formData = new FormData(form);
    console.log(`Submitting reply to comment: ${commentId}`);
    console.log(`Reply content: ${formData.get('content')}`);
    
    // Validate required fields
    if (!formData.get('content') || !formData.get('content').trim()) {
        showAlert('Reply content cannot be empty', 'error');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Post Reply';
        }
        return;
    }
    
    // Send the request
    fetch(`/api/comments/${commentId}/reply`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Reply successfully added:', data);
            
            // Reset form
            form.reset();
            
            // Hide the form
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            if (replyForm) {
                replyForm.style.display = 'none';
            }
            
            // Add the new reply to the DOM
            if (data.reply) {
                const repliesContainer = document.getElementById(`replies-${commentId}`);
                if (repliesContainer) {
                    // Create a new reply element and append it
                    const replyEl = createReplyElement(data.reply);
                    repliesContainer.appendChild(replyEl);
                    
                    // Scroll to the new reply with a slight delay to ensure it's rendered
                    setTimeout(() => {
                        replyEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        
                        // Highlight the new reply briefly
                        replyEl.classList.add('comment-highlight');
                        setTimeout(() => {
                            replyEl.classList.remove('comment-highlight');
                        }, 3000);
                    }, 100);
                }
            }
            
            showAlert('Reply posted successfully!', 'success');
        } else {
            showAlert(data.message || 'Error posting reply', 'error');
        }
        
        // Reset button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Post Reply';
        }
    })
    .catch(error => {
        console.error('Error submitting reply:', error);
        showAlert('Failed to post reply. Please try again.', 'error');
        
        // Reset button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Post Reply';
        }
    });
}

/**
 * Like a comment
 * @param {string} commentId - The ID of the comment
 */
function likeComment(commentId) {
    console.log(`Liking comment: ${commentId}`);
    
    // Get the CSRF token
    const csrfToken = getCsrfToken();
    
    // Update button UI immediately to provide feedback
    const likeBtn = document.querySelector(`.like-btn[data-comment-id="${commentId}"]`);
    const dislikeBtn = document.querySelector(`.dislike-btn[data-comment-id="${commentId}"]`);
    
    if (likeBtn) {
        // Add loading state
        likeBtn.classList.add('btn-progress');
        
        // Predict the UI change for better responsiveness
        if (likeBtn.classList.contains('active')) {
            // Predict the action will be unlike
            likeBtn.classList.remove('btn-primary', 'active');
            likeBtn.classList.add('btn-outline-primary');
        } else {
            // Predict the action will be like
            likeBtn.classList.remove('btn-outline-primary');
            likeBtn.classList.add('btn-primary', 'active');
            
            // If the comment was disliked, predict removing the dislike
            if (dislikeBtn && dislikeBtn.classList.contains('active')) {
                dislikeBtn.classList.remove('btn-danger', 'active');
                dislikeBtn.classList.add('btn-outline-danger');
            }
        }
    }
    
    // Send the request
    fetch(`/api/comments/${commentId}/like`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: `csrf_token=${encodeURIComponent(csrfToken)}`,
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('API response data:', data);
        
        if (data.success) {
            // Update the UI
            updateLikeDislikeUI(commentId, 'comment', data);
        } else {
            console.error('Error liking comment:', data.message);
            showAlert(`Error: ${data.message}`, 'error');
            
            // Revert UI changes
            if (likeBtn) {
                likeBtn.classList.remove('btn-progress');
            }
        }
    })
    .catch(error => {
        console.error('Error sending like request:', error);
        showAlert('Failed to like comment. Please try again.', 'error');
        
        // Revert UI changes
        if (likeBtn) {
            likeBtn.classList.remove('btn-progress');
        }
    });
}

/**
 * Dislike a comment
 * @param {string} commentId - The ID of the comment
 */
function dislikeComment(commentId) {
    console.log(`Disliking comment: ${commentId}`);
    
    // Get the CSRF token
    const csrfToken = getCsrfToken();
    
    // Update button UI immediately to provide feedback
    const dislikeBtn = document.querySelector(`.dislike-btn[data-comment-id="${commentId}"]`);
    const likeBtn = document.querySelector(`.like-btn[data-comment-id="${commentId}"]`);
    
    if (dislikeBtn) {
        // Add loading state
        dislikeBtn.classList.add('btn-progress');
        
        // Predict the UI change for better responsiveness
        if (dislikeBtn.classList.contains('active')) {
            // Predict the action will be undislike
            dislikeBtn.classList.remove('btn-danger', 'active');
            dislikeBtn.classList.add('btn-outline-danger');
        } else {
            // Predict the action will be dislike
            dislikeBtn.classList.remove('btn-outline-danger');
            dislikeBtn.classList.add('btn-danger', 'active');
            
            // If the comment was liked, predict removing the like
            if (likeBtn && likeBtn.classList.contains('active')) {
                likeBtn.classList.remove('btn-primary', 'active');
                likeBtn.classList.add('btn-outline-primary');
            }
        }
    }
    
    // Send the request
    fetch(`/api/comments/${commentId}/dislike`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: `csrf_token=${encodeURIComponent(csrfToken)}`,
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('API response data:', data);
        
        if (data.success) {
            // Update the UI
            updateLikeDislikeUI(commentId, 'comment', data);
        } else {
            console.error('Error disliking comment:', data.message);
            showAlert(`Error: ${data.message}`, 'error');
            
            // Revert UI changes
            if (dislikeBtn) {
                dislikeBtn.classList.remove('btn-progress');
            }
        }
    })
    .catch(error => {
        console.error('Error sending dislike request:', error);
        showAlert('Failed to dislike comment. Please try again.', 'error');
        
        // Revert UI changes
        if (dislikeBtn) {
            dislikeBtn.classList.remove('btn-progress');
        }
    });
}

/**
 * Like a reply
 * @param {string} replyId - The ID of the reply
 */
function likeReply(replyId) {
    if (!replyId || replyId === 'undefined' || replyId === 'null') {
        console.error('Invalid reply ID for like action:', replyId);
        showAlert('Error: Invalid reply ID', 'error');
        return;
    }
    
    const csrfToken = getCsrfToken();
    
    fetch(`/api/replies/${replyId}/like`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: `csrf_token=${encodeURIComponent(csrfToken)}`,
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            updateLikeDislikeUI(replyId, 'reply', data);
        } else {
            showAlert(data.message || 'Error processing like', 'error');
        }
    })
    .catch(error => {
        console.error('Error liking reply:', error);
        showAlert('An error occurred while processing your action', 'error');
    });
}

/**
 * Dislike a reply
 * @param {string} replyId - The ID of the reply
 */
function dislikeReply(replyId) {
    if (!replyId || replyId === 'undefined' || replyId === 'null') {
        console.error('Invalid reply ID for dislike action:', replyId);
        showAlert('Error: Invalid reply ID', 'error');
        return;
    }
    
    const csrfToken = getCsrfToken();
    
    fetch(`/api/replies/${replyId}/dislike`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: `csrf_token=${encodeURIComponent(csrfToken)}`,
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            updateLikeDislikeUI(replyId, 'reply', data);
        } else {
            showAlert(data.message || 'Error processing dislike', 'error');
        }
    })
    .catch(error => {
        console.error('Error disliking reply:', error);
        showAlert('An error occurred while processing your action', 'error');
    });
}

/**
 * Update the UI for like/dislike buttons
 * @param {string} id - The ID of the comment or reply
 * @param {string} type - Either 'comment' or 'reply'
 * @param {Object} data - Response data from the API
 */
function updateLikeDislikeUI(id, type, data) {
    const container = document.getElementById(`${type}-${id}`);
    if (!container) {
        console.error(`Container ${type}-${id} not found`);
        return;
    }
    
    // Update like button
    const likeBtn = container.querySelector('.like-btn');
    if (likeBtn) {
        // Update count
        const likesCount = likeBtn.querySelector('.likes-count');
        if (likesCount) {
            likesCount.textContent = data.likes_count || 0;
        }
        
        // Update button state
        if (data.user_liked) {
            likeBtn.classList.add('btn-primary', 'active');
            likeBtn.classList.remove('btn-outline-primary');
        } else {
            likeBtn.classList.remove('btn-primary', 'active');
            likeBtn.classList.add('btn-outline-primary');
        }
    }
    
    // Update dislike button
    const dislikeBtn = container.querySelector('.dislike-btn');
    if (dislikeBtn) {
        // Update count
        const dislikesCount = dislikeBtn.querySelector('.dislikes-count');
        if (dislikesCount) {
            dislikesCount.textContent = data.dislikes_count || 0;
        }
        
        // Update button state
        if (data.user_disliked) {
            dislikeBtn.classList.add('btn-danger', 'active');
            dislikeBtn.classList.remove('btn-outline-danger');
        } else {
            dislikeBtn.classList.remove('btn-danger', 'active');
            dislikeBtn.classList.add('btn-outline-danger');
        }
    }
    
    // Add a visual feedback animation
    const feedbackAnimation = (elem) => {
        elem.classList.add('btn-animation');
        setTimeout(() => {
            elem.classList.remove('btn-animation');
        }, 300);
    };
    
    if (data.user_liked) {
        feedbackAnimation(likeBtn);
    } else if (data.user_disliked) {
        feedbackAnimation(dislikeBtn);
    }
}

/**
 * Display an alert message to the user
 * @param {string} message - The message to display
 * @param {string} type - The type of alert ('success', 'error', 'info', 'warning')
 */
function showAlert(message, type = 'info') {
    // Create alert container if it doesn't exist
    let alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'alert-container';
        alertContainer.className = 'fixed top-4 right-4 z-50';
        document.body.appendChild(alertContainer);
    }
    
    // Create the alert element
    const alert = document.createElement('div');
    alert.className = `alert ${getAlertClass(type)} shadow-lg mb-3 max-w-sm`;
    alert.innerHTML = `
        <div>
            <span>${message}</span>
        </div>
        <button class="btn btn-sm btn-ghost" onclick="this.parentElement.remove();">×</button>
    `;
    
    // Add to container
    alertContainer.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.classList.add('fade-out');
        setTimeout(() => alert.remove(), 500);
    }, 5000);
}

/**
 * Get the appropriate alert class based on type
 * @param {string} type - The type of alert
 * @returns {string} - CSS class
 */
function getAlertClass(type) {
    switch (type) {
        case 'success': return 'alert-success';
        case 'error': return 'alert-error';
        case 'warning': return 'alert-warning';
        default: return 'alert-info';
    }
}

/**
 * Get the CSRF token from the page
 * @returns {string} - The CSRF token
 */
function getCsrfToken() {
    const tokenInput = document.querySelector('input[name="csrf_token"]');
    if (tokenInput) {
        return tokenInput.value;
    }
    return '';
}

/**
 * Escape HTML to prevent XSS
 * @param {string} unsafe - Unsafe string that might contain HTML
 * @returns {string} - Escaped string
 */
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Get the initials from a name
 * @param {string} name - The name to get initials from
 * @returns {string} - The initials (up to 2 characters)
 */
function getInitials(name) {
    if (!name) return '?';
    
    const parts = name.split(' ');
    if (parts.length === 1) {
        return name.charAt(0).toUpperCase();
    }
    
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

/**
 * Add CSS for button animations
 */
function addButtonAnimationStyles() {
    if (!document.getElementById('button-animation-styles')) {
        const style = document.createElement('style');
        style.id = 'button-animation-styles';
        style.textContent = `
            @keyframes btn-pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.15); }
                100% { transform: scale(1); }
            }
            
            .btn-animation {
                animation: btn-pulse 0.3s ease;
            }
            
            .like-btn.active, .dislike-btn.active {
                transform: scale(1.05);
                font-weight: bold;
            }
            
            .like-btn:hover, .dislike-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
        `;
        document.head.appendChild(style);
    }
}

/**
 * Delete a comment
 * @param {string} commentId - The ID of the comment to delete
 */
function deleteComment(commentId) {
    // Get CSRF token
    const token = getCsrfToken();
    if (!token) {
        showAlert('CSRF token missing. Please refresh the page.', 'error');
        return;
    }
    
    // Create form data
    const formData = new FormData();
    formData.append('csrf_token', token);
    
    // Send delete request
    fetch(`/api/comments/${commentId}/delete`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Find comment element
            const commentEl = document.getElementById(`comment-${commentId}`);
            if (commentEl) {
                // Add fading out animation
                commentEl.classList.add('comment-deleted');
                commentEl.classList.add('comment-removing');
                
                // Remove after animation completes
                setTimeout(() => {
                    commentEl.remove();
                    
                    // Check if there are no more comments
                    const commentsContainer = document.getElementById('comments-list');
                    if (commentsContainer && commentsContainer.children.length === 0) {
                        commentsContainer.innerHTML = '<p class="text-center my-4 text-muted">No comments yet. Be the first to comment!</p>';
                    }
                }, 500);
            }
            
            showAlert('Comment deleted successfully', 'success');
        } else {
            showAlert(data.message || 'Error deleting comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error deleting comment:', error);
        showAlert('Failed to delete comment. Please try again.', 'error');
    });
}

/**
 * Report a comment
 * @param {Event} event - Form submit event
 */
function reportComment(event) {
    event.preventDefault();
    
    const form = event.target;
    const commentId = form.querySelector('[name="comment_id"]').value;
    const reason = form.querySelector('[name="reason"]').value;
    
    // Validate the reason
    if (!reason || reason.trim() === '') {
        showAlert('Please provide a reason for the report', 'error');
        return;
    }
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    }
    
    // Create form data
    const formData = new FormData(form);
    
    // Send report request
    fetch(`/api/comments/${commentId}/report`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // Reset form state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Submit Report';
        }
        
        if (data.success) {
            // Close the modal
            const reportModal = document.getElementById('reportCommentModal');
            if (reportModal) {
                const modalInstance = bootstrap.Modal.getInstance(reportModal);
                if (modalInstance) {
                    modalInstance.hide();
                }
            }
            
            // Reset form
            form.reset();
            
            showAlert(data.message || 'Comment reported successfully', 'success');
        } else {
            showAlert(data.message || 'Error reporting comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error reporting comment:', error);
        showAlert('Failed to report comment. Please try again.', 'error');
        
        // Reset button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Submit Report';
        }
    });
}

// Helper functions to route to correct like/dislike functions based on type
function likeItem(id, type, button) {
    if (type === 'comment') {
        likeComment(id);
    } else if (type === 'reply') {
        likeReply(id);
    }
}

function dislikeItem(id, type, button) {
    if (type === 'comment') {
        dislikeComment(id);
    } else if (type === 'reply') {
        dislikeReply(id);
    }
}
