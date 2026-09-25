// Utility functions for EdlioX

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Handle file upload preview
function handleFileUpload(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const fileSize = formatFileSize(file.size);
        const fileName = file.name;
        
        // Update file info display
        const fileInfo = document.getElementById('fileInfo');
        if (fileInfo) {
            fileInfo.textContent = `${fileName} (${fileSize})`;
        }
        
        // Validate file size (max 100MB)
        if (file.size > 100 * 1024 * 1024) {
            alert('File size must be less than 100MB');
            input.value = '';
            if (fileInfo) {
                fileInfo.textContent = '';
            }
            return false;
        }
        
        return true;
    }
    return false;
}

// Handle form submission
function handleFormSubmit(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
            }
        });
    }
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize file upload handlers
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            handleFileUpload(this);
        });
    });
    
    // Initialize form submission handlers
    handleFormSubmit('uploadForm');
    handleFormSubmit('discussionForm');
    handleFormSubmit('commentForm');
});

// Handle search suggestions
let searchTimeout;
const searchInput = document.querySelector('input[name="q"]');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(function() {
            const query = searchInput.value.trim();
            if (query.length >= 2) {
                fetch(`/api/search?q=${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        const suggestions = document.getElementById('searchSuggestions');
                        if (suggestions) {
                            suggestions.innerHTML = '';
                            data.forEach(item => {
                                const div = document.createElement('div');
                                div.className = 'list-group-item';
                                div.innerHTML = `
                                    <h6 class="mb-1">${item.title}</h6>
                                    <p class="mb-1">${item.description || item.content}</p>
                                    <small class="text-muted">${item.type === 'resource' ? 'Resource' : 'Discussion'}</small>
                                `;
                                div.addEventListener('click', function() {
                                    window.location.href = item.url;
                                });
                                suggestions.appendChild(div);
                            });
                            suggestions.style.display = data.length > 0 ? 'block' : 'none';
                        }
                    })
                    .catch(error => console.error('Error fetching search suggestions:', error));
            } else {
                const suggestions = document.getElementById('searchSuggestions');
                if (suggestions) {
                    suggestions.style.display = 'none';
                }
            }
        }, 300);
    });
}

// Handle infinite scroll
let isLoading = false;
let currentPage = 1;
const loadMoreButton = document.getElementById('loadMore');
if (loadMoreButton) {
    loadMoreButton.addEventListener('click', function() {
        if (!isLoading) {
            isLoading = true;
            currentPage++;
            
            const resourceType = this.dataset.type;
            const url = `/api/${resourceType}?page=${currentPage}`;
            
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById(`${resourceType}Container`);
                    if (container && data.items.length > 0) {
                        data.items.forEach(item => {
                            // Add new items to the container
                            // Implementation depends on the resource type
                        });
                        
                        if (!data.has_more) {
                            loadMoreButton.style.display = 'none';
                        }
                    }
                })
                .catch(error => console.error('Error loading more items:', error))
                .finally(() => {
                    isLoading = false;
                });
        }
    });
}

// Function to confirm and handle comment deletion
function confirmDeleteComment(commentId, discussionId) {
    if (confirm('Are you sure you want to delete this comment? This action cannot be undone.')) {
        // Create a form to submit the delete request
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/discussions/comments/${commentId}/delete`;
        form.style.display = 'none';
        
        // Add CSRF token
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = document.querySelector('meta[name="csrf-token"]').content;
        form.appendChild(csrfInput);
        
        // Append form to body and submit
        document.body.appendChild(form);
        form.submit();
    }
}

// Function to open the edit comment modal
function openEditComment(commentId, discussionId, linkElement) {
    // Get the comment content
    const commentCard = linkElement.closest('.card');
    const contentElement = commentCard.querySelector('.answer-content');
    
    // Get the raw HTML content (we need to handle the case where it might contain Markdown)
    // For simplicity, we'll just do basic cleanup - in a real app, you might need a more sophisticated approach
    let commentContent = contentElement.innerHTML.trim();
    
    // Basic cleanup - remove common HTML tags from rich text editors
    commentContent = commentContent
        .replace(/<p>(.*?)<\/p>/g, '$1\n\n')
        .replace(/<br\s*\/?>/g, '\n')
        .replace(/<div>(.*?)<\/div>/g, '$1\n')
        .replace(/<li>(.*?)<\/li>/g, '- $1\n')
        .replace(/<\/?[^>]+(>|$)/g, ''); // Remove remaining HTML tags
        
    // Decode HTML entities
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = commentContent;
    commentContent = tempDiv.textContent;
    
    // Update the form action - Fix URL path to match server routes
    const form = document.getElementById('editCommentForm');
    form.action = `/discussions/comments/${commentId}/edit`;
    
    // Set the textarea content
    const textarea = document.getElementById('editCommentContent');
    textarea.value = commentContent;
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('editCommentModal'));
    modal.show();
} 