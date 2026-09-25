// Get CSRF token from meta tag
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

// Discussion social interactions handling
const DiscussionManager = {
    // Vote handling
    handleVote: async function(discussionId, voteType) {
        try {
            const response = await fetch(`/api/discussions/${discussionId}/vote`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ vote_type: voteType })
            });
            const data = await response.json();
            if (response.ok) {
                // Update vote counts and UI
                this.updateVoteUI(discussionId, data.votes, data.score);
                return true;
            }
            if (response.status === 401) {
                window.location.href = '/login';
                return false;
            }
            throw new Error(data.error || 'Vote failed');
        } catch (error) {
            console.error('Vote error:', error);
            alert(error.message || 'Failed to register vote. Please try again.');
            return false;
        }
    },

    // Comment vote handling
    handleCommentVote: async function(discussionId, commentId, voteType) {
        try {
            const response = await fetch(`/api/discussions/${discussionId}/comments/${commentId}/vote`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ vote_type: voteType })
            });
            const data = await response.json();
            if (response.ok) {
                // Update comment vote UI
                this.updateCommentVoteUI(commentId, data.votes, data.score);
                return true;
            }
            if (response.status === 401) {
                window.location.href = '/login';
                return false;
            }
            throw new Error(data.error || 'Comment vote failed');
        } catch (error) {
            console.error('Comment vote error:', error);
            alert(error.message || 'Failed to vote on comment. Please try again.');
            return false;
        }
    },

    // Share functionality
    shareDiscussion: function(discussionId, title, slug) {
        const shareUrl = `${window.location.origin}/discussions/${slug}`;
        
        if (navigator.share) {
            // Use Web Share API if available
            navigator.share({
                title: title,
                text: 'Check out this discussion!',
                url: shareUrl
            }).catch(console.error);
        } else {
            // Fallback to clipboard copy
            navigator.clipboard.writeText(shareUrl)
                .then(() => alert('Link copied to clipboard!'))
                .catch(() => {
                    // Fallback for clipboard API failure
                    const tempInput = document.createElement('input');
                    tempInput.value = shareUrl;
                    document.body.appendChild(tempInput);
                    tempInput.select();
                    document.execCommand('copy');
                    document.body.removeChild(tempInput);
                    alert('Link copied to clipboard!');
                });
        }
    },

    // UI Updates
    updateVoteUI: function(discussionId, votes, score) {
        const upvoteBtn = document.querySelector(`#discussion-${discussionId} .upvote-btn`);
        const downvoteBtn = document.querySelector(`#discussion-${discussionId} .downvote-btn`);
        const scoreElement = document.querySelector(`#discussion-${discussionId} .score`);

        if (upvoteBtn && downvoteBtn && scoreElement) {
            // Get current user ID from the page
            const currentUserId = document.querySelector('meta[name="user-id"]')?.content;
            
            upvoteBtn.classList.toggle('active', votes.up.includes(currentUserId));
            downvoteBtn.classList.toggle('active', votes.down.includes(currentUserId));
            scoreElement.textContent = score;

            // Update button states
            upvoteBtn.disabled = false;
            downvoteBtn.disabled = false;
        }
    },

    updateCommentVoteUI: function(commentId, votes, score) {
        const upvoteBtn = document.querySelector(`#comment-${commentId} .upvote-btn`);
        const downvoteBtn = document.querySelector(`#comment-${commentId} .downvote-btn`);
        const scoreElement = document.querySelector(`#comment-${commentId} .score`);

        if (upvoteBtn && downvoteBtn && scoreElement) {
            // Get current user ID from the page
            const currentUserId = document.querySelector('meta[name="user-id"]')?.content;
            
            upvoteBtn.classList.toggle('active', votes.up.includes(currentUserId));
            downvoteBtn.classList.toggle('active', votes.down.includes(currentUserId));
            scoreElement.textContent = score;

            // Update button states
            upvoteBtn.disabled = false;
            downvoteBtn.disabled = false;
        }
    },

    // Comment submission
    submitComment: async function(discussionId, content, parentId = null) {
        try {
            const response = await fetch(`/api/discussions/${discussionId}/comments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    content: content,
                    parent_id: parentId
                })
            });
            const data = await response.json();
            if (response.ok) {
                // Clear the comment input
                const commentInput = document.querySelector(parentId ? `#reply-${parentId}` : '#comment-input');
                if (commentInput) {
                    commentInput.value = '';
                }
                // Hide reply form if this was a reply
                if (parentId) {
                    const replyForm = document.querySelector(`#reply-form-${parentId}`);
                    if (replyForm) {
                        replyForm.style.display = 'none';
                    }
                }
                // Refresh comments section or append new comment
                this.appendNewComment(data.comment);
                return true;
            }
            if (response.status === 401) {
                window.location.href = '/login';
                return false;
            }
            throw new Error(data.error || 'Failed to submit comment');
        } catch (error) {
            console.error('Comment submission error:', error);
            alert(error.message || 'Failed to submit comment. Please try again.');
            return false;
        }
    },

    // Helper function to append new comment to the DOM
    appendNewComment: function(comment) {
        const commentsContainer = document.querySelector('.comments-container');
        const commentTemplate = this.createCommentElement(comment);
        
        if (comment.parent_id) {
            const parentComment = document.querySelector(`#comment-${comment.parent_id} .replies`);
            if (parentComment) {
                parentComment.appendChild(commentTemplate);
            }
        } else {
            commentsContainer.insertBefore(commentTemplate, commentsContainer.firstChild);
        }
    },

    // Helper function to create comment DOM element
    createCommentElement: function(comment) {
        const div = document.createElement('div');
        div.id = `comment-${comment.id}`;
        div.className = 'comment';
        div.innerHTML = `
            <div class="comment-content">
                <div class="comment-header">
                    <span class="comment-author">${comment.author.username}</span>
                    <span class="comment-date">${new Date(comment.created_at).toLocaleDateString()}</span>
                </div>
                <div class="comment-text">${comment.content}</div>
                <div class="comment-actions">
                    <button class="upvote-btn" onclick="DiscussionManager.handleCommentVote('${comment.discussion_id}', '${comment.id}', 'up')">
                        <i class="fas fa-arrow-up"></i>
                    </button>
                    <span class="score">0</span>
                    <button class="downvote-btn" onclick="DiscussionManager.handleCommentVote('${comment.discussion_id}', '${comment.id}', 'down')">
                        <i class="fas fa-arrow-down"></i>
                    </button>
                    <button class="reply-btn" onclick="showReplyForm('${comment.id}')">
                        Reply
                    </button>
                </div>
            </div>
            <div class="replies"></div>
            <div id="reply-form-${comment.id}" class="reply-form" style="display: none;">
                <textarea id="reply-${comment.id}" class="reply-input" placeholder="Write your reply..."></textarea>
                <button onclick="DiscussionManager.submitComment('${comment.discussion_id}', document.querySelector('#reply-${comment.id}').value, '${comment.id}')">Submit Reply</button>
            </div>
        `;
        return div;
    }
};

// Helper function to show/hide reply form
function showReplyForm(commentId) {
    const replyForm = document.querySelector(`#reply-form-${commentId}`);
    if (replyForm) {
        replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
    }
}