/**
 * Discussion System Service Worker
 * Provides caching and offline support
 */

const CACHE_NAME = 'discussion-cache-v1';
const STATIC_ASSETS = [
  '/static/js/discussion.js',
  '/static/js/discussion-ui.js',
  '/static/js/discussion-main.js',
  '/static/css/bootstrap.min.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/fonts/font-awesome/css/all.min.css',
  // Add other static assets here
];

// Install event - cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network first, then cache for API calls
// Cache first, then network for static assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  // For API calls, use network first strategy
  if (url.pathname.includes('/api/')) {
    event.respondWith(networkFirstStrategy(event.request));
  } 
  // For static assets, use cache first strategy
  else if (STATIC_ASSETS.some(asset => url.pathname.endsWith(asset)) || 
           url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirstStrategy(event.request));
  }
  // For HTML pages, use network first
  else if (url.pathname.endsWith('/') || 
           url.pathname.endsWith('.html') || 
           url.pathname.includes('/discussions')) {
    event.respondWith(networkFirstStrategy(event.request));
  }
});

/**
 * Network first strategy
 * Try network, fall back to cache, then offline page
 */
async function networkFirstStrategy(request) {
  try {
    // Try to get from network
    const networkResponse = await fetch(request);
    
    // Clone the response
    const responseToCache = networkResponse.clone();
    
    // Cache the response (only if successful)
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, responseToCache);
    }
    
    return networkResponse;
  } catch (error) {
    // Network failed, try to get from cache
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // If the request URL is an API call, return a custom offline response
    if (request.url.includes('/api/')) {
      return createOfflineResponse(request);
    }
    
    // For pages, show the offline page
    return caches.match('/offline.html') || createOfflineResponse(request);
  }
}

/**
 * Cache first strategy
 * Try cache, fall back to network
 */
async function cacheFirstStrategy(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    // Not in cache, get from network
    const networkResponse = await fetch(request);
    
    // Cache the new response
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, networkResponse.clone());
    
    return networkResponse;
  } catch (error) {
    // Network failed, return appropriate offline response
    return createOfflineResponse(request);
  }
}

/**
 * Create offline response for API calls
 */
function createOfflineResponse(request) {
  // For discussions API, return empty list with offline indicator
  if (request.url.includes('/api/discussions')) {
    return new Response(JSON.stringify({
      discussions: [],
      total: 0,
      pages: 0,
      current_page: 1,
      offline: true
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // Default offline response
  return new Response('Offline - No cached data available', {
    status: 503,
    statusText: 'Service Unavailable',
    headers: new Headers({
      'Content-Type': 'text/plain'
    })
  });
}

// Handle sync events for offline comment posting
self.addEventListener('sync', event => {
  if (event.tag === 'post-comment') {
    event.waitUntil(syncPendingComments());
  } else if (event.tag === 'post-discussion') {
    event.waitUntil(syncPendingDiscussions());
  }
});

/**
 * Sync pending comments when connection is restored
 */
async function syncPendingComments() {
  try {
    // Get pending comments from IndexedDB
    const db = await openDatabase();
    const pendingComments = await getAllPendingComments(db);
    
    // Post each comment
    const syncPromises = pendingComments.map(async comment => {
      try {
        const response = await fetch(`/discussions/api/discussions/${comment.discussionId}/comments`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ content: comment.content })
        });
        
        if (response.ok) {
          // Remove from pending queue
          await removePendingComment(db, comment.id);
          return true;
        }
        
        return false;
      } catch (error) {
        console.error('Failed to sync comment:', error);
        return false;
      }
    });
    
    return Promise.all(syncPromises);
  } catch (error) {
    console.error('Failed to sync comments:', error);
  }
}

/**
 * Sync pending discussions when connection is restored
 */
async function syncPendingDiscussions() {
  try {
    // Get pending discussions from IndexedDB
    const db = await openDatabase();
    const pendingDiscussions = await getAllPendingDiscussions(db);
    
    // Post each discussion
    const syncPromises = pendingDiscussions.map(async discussion => {
      try {
        const response = await fetch('/discussions/api/discussions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(discussion)
        });
        
        if (response.ok) {
          // Remove from pending queue
          await removePendingDiscussion(db, discussion.id);
          return true;
        }
        
        return false;
      } catch (error) {
        console.error('Failed to sync discussion:', error);
        return false;
      }
    });
    
    return Promise.all(syncPromises);
  } catch (error) {
    console.error('Failed to sync discussions:', error);
  }
}

// IndexedDB helpers for offline data storage
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('DiscussionsOfflineDB', 1);
    
    request.onupgradeneeded = event => {
      const db = event.target.result;
      
      // Create object stores
      if (!db.objectStoreNames.contains('pendingComments')) {
        db.createObjectStore('pendingComments', { keyPath: 'id', autoIncrement: true });
      }
      
      if (!db.objectStoreNames.contains('pendingDiscussions')) {
        db.createObjectStore('pendingDiscussions', { keyPath: 'id', autoIncrement: true });
      }
    };
    
    request.onsuccess = event => resolve(event.target.result);
    request.onerror = event => reject(event.target.error);
  });
}

function getAllPendingComments(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pendingComments'], 'readonly');
    const store = transaction.objectStore('pendingComments');
    const request = store.getAll();
    
    request.onsuccess = event => resolve(event.target.result);
    request.onerror = event => reject(event.target.error);
  });
}

function getAllPendingDiscussions(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pendingDiscussions'], 'readonly');
    const store = transaction.objectStore('pendingDiscussions');
    const request = store.getAll();
    
    request.onsuccess = event => resolve(event.target.result);
    request.onerror = event => reject(event.target.error);
  });
}

function removePendingComment(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pendingComments'], 'readwrite');
    const store = transaction.objectStore('pendingComments');
    const request = store.delete(id);
    
    request.onsuccess = event => resolve();
    request.onerror = event => reject(event.target.error);
  });
}

function removePendingDiscussion(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pendingDiscussions'], 'readwrite');
    const store = transaction.objectStore('pendingDiscussions');
    const request = store.delete(id);
    
    request.onsuccess = event => resolve();
    request.onerror = event => reject(event.target.error);
  });
} 