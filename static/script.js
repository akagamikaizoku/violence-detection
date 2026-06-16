// Dashboard Configuration
const CONFIG = {
    refreshInterval: 3000,
    maxLogLines: 1000,
    autoScroll: true,
    isPaused: false
    };
  
  // State Management
  let currentFilter = 'all';
  let searchTerm = '';
  let logCache = [];
  let refreshTimer = null;
  let stats = {
    total: 0,
    alert: 0,
    warning: 0,
    info: 0,
    debug: 0,
    error: 0
  };
  
  // DOM Elements
  const elements = {
    logBox: null,
    searchInput: null,
    statusDot: null,
    statusText: null,
    autoScrollBtn: null,
    pauseBtn: null,
    statCards: {}
  };
  
// Initialize Dashboard
document.addEventListener('DOMContentLoaded', function() {
  initializeTheme();
  initializeElements();
  setupEventListeners();
  startLogFetching();
  updateConnectionStatus('connected');
  addWelcomeMessage();
});

// Theme management
function initializeTheme() {
  const themeToggle = document.getElementById('themeToggle');
  const savedTheme = localStorage.getItem('theme') || 'light';
  
  if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
  }
  
  themeToggle.addEventListener('click', toggleTheme);
}

function toggleTheme() {
  const themeToggle = document.getElementById('themeToggle');
  document.body.classList.toggle('dark-mode');
  
  if (document.body.classList.contains('dark-mode')) {
    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    localStorage.setItem('theme', 'dark');
  } else {
    themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
    localStorage.setItem('theme', 'light');
  }
}

// Welcome message
function addWelcomeMessage() {
  setTimeout(() => {
    const welcomeMsg = document.createElement('div');
    welcomeMsg.className = 'log-line info';
    welcomeMsg.innerHTML = '<span class="log-timestamp">' + new Date().toLocaleTimeString() + '</span> [INFO] Violence Detection System initialized and ready';
    if (elements.logBox) {
      const loadingSpinner = elements.logBox.querySelector('.loading-spinner');
      if (loadingSpinner) {
        loadingSpinner.remove();
      }
      elements.logBox.appendChild(welcomeMsg);
    }
  }, 500);
}  // Initialize DOM element references
  function initializeElements() {
    elements.logBox = document.getElementById('log-box');
    elements.searchInput = document.getElementById('search');
    elements.statusDot = document.getElementById('status-dot');
    elements.statusText = document.getElementById('status-text');
    elements.autoScrollBtn = document.getElementById('auto-scroll-btn');
    elements.pauseBtn = document.getElementById('pause-btn');
    
    // Initialize stat card references
    elements.statCards = {
      total: document.getElementById('total-logs'),
      alert: document.getElementById('alert-count'),
      warning: document.getElementById('warning-count'),
      info: document.getElementById('info-count')
    };
  }
  
  // Setup event listeners
  function setupEventListeners() {
    // Search input with debouncing
    let searchTimeout;
    elements.searchInput.addEventListener('input', function() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchTerm = this.value.toLowerCase();
        renderLogs();
      }, 300);
    });
  
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
      // Ctrl/Cmd + R for refresh
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        fetchLogs();
      }
      
      // Ctrl/Cmd + D for download
      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        downloadLogs();
      }
      
      // Space for pause/unpause
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        togglePause();
      }
    });
  
    // Visibility change handling
    document.addEventListener('visibilitychange', function() {
      if (document.hidden) {
        pauseRefreshing();
      } else {
        resumeRefreshing();
      }
    });
  }
  
  // Main log fetching function
  async function fetchLogs() {
    if (CONFIG.isPaused) return;
    
    try {
      updateConnectionStatus('connecting');
      
      const response = await fetch('/logs');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data && data.logs) {
        processLogData(data.logs);
        updateConnectionStatus('connected');
      } else {
        throw new Error('Invalid response format');
      }
      
    } catch (error) {
      console.error('Log fetch error:', error);
      updateConnectionStatus('disconnected');
      displayError(`Failed to fetch logs: ${error.message}`);
    }
  }
  
  // Process and cache log data
  function processLogData(rawLogs) {
    const lines = rawLogs.split('\n').filter(line => line.trim());
    
    // Update cache with new lines
    logCache = lines.map(line => ({
      text: line,
      timestamp: extractTimestamp(line),
      type: detectLogType(line),
      id: generateLineId(line)
    }));
  
    // Limit cache size
    if (logCache.length > CONFIG.maxLogLines) {
      logCache = logCache.slice(-CONFIG.maxLogLines);
    }
  
    updateStats();
    renderLogs();
  }
  
  // Extract timestamp from log line
  function extractTimestamp(line) {
    const timestampMatch = line.match(/^\[?(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})/);
    return timestampMatch ? timestampMatch[1] : new Date().toISOString().slice(0, 19);
  }
  
  // Detect log type from content
  function detectLogType(line) {
    const upperLine = line.toUpperCase();
    
    if (upperLine.includes('ALERT') || upperLine.includes('CRITICAL')) return 'alert';
    if (upperLine.includes('WARNING') || upperLine.includes('WARN')) return 'warning';
    if (upperLine.includes('ERROR') || upperLine.includes('FATAL')) return 'error';
    if (upperLine.includes('DEBUG')) return 'debug';
    if (upperLine.includes('INFO')) return 'info';
    
    return 'info'; // default
  }
  
  // Generate unique ID for log line
  function generateLineId(line) {
    return btoa(line + Date.now()).slice(0, 16);
  }
  
  // Update statistics
  function updateStats() {
    stats = {
      total: logCache.length,
      alert: 0,
      warning: 0,
      info: 0,
      debug: 0,
      error: 0
    };
  
    logCache.forEach(log => {
      stats[log.type]++;
    });
  
    // Update UI
    if (elements.statCards.total) elements.statCards.total.textContent = stats.total;
    if (elements.statCards.alert) elements.statCards.alert.textContent = stats.alert;
    if (elements.statCards.warning) elements.statCards.warning.textContent = stats.warning;
    if (elements.statCards.info) elements.statCards.info.textContent = stats.info + stats.debug + stats.error;
  }
  
  // Render logs to the display
  function renderLogs() {
    if (!elements.logBox) return;
  
    const filteredLogs = logCache.filter(log => {
      // Apply type filter
      if (currentFilter !== 'all' && log.type !== currentFilter) {
        return false;
      }
      
      // Apply search filter
      if (searchTerm && !log.text.toLowerCase().includes(searchTerm)) {
        return false;
      }
      
      return true;
    });
  
    if (filteredLogs.length === 0) {
      elements.logBox.innerHTML = '<div class="log-line info">No logs match current filters</div>';
      return;
    }
  
    const fragment = document.createDocumentFragment();
    
    filteredLogs.forEach(log => {
      const logElement = createLogElement(log);
      fragment.appendChild(logElement);
    });
  
    elements.logBox.innerHTML = '';
    elements.logBox.appendChild(fragment);
  
    // Auto-scroll to bottom
    if (CONFIG.autoScroll) {
      elements.logBox.scrollTop = elements.logBox.scrollHeight;
    }
  }
  
  // Create individual log element
  function createLogElement(log) {
    const div = document.createElement('div');
    div.className = `log-line ${log.type}`;
    div.setAttribute('data-id', log.id);
    
    // Format the log line with timestamp highlighting
    const formattedText = formatLogLine(log.text, log.timestamp);
    div.innerHTML = formattedText;
    
    return div;
  }
  
  function formatLogLine(text, timestamp) {
    const timestampRegex = /(\[?\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\]]*\]?)/g;
    return text.replace(timestampRegex, '<span class="log-timestamp">$1</span>');
  }
  
  // Filter functions
  function setFilter(filterType) {
    currentFilter = filterType;
    
    // Update filter button states
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    document.querySelector(`[data-filter="${filterType}"]`).classList.add('active');
    
    renderLogs();
  }
  
  function applyFilter() {
    searchTerm = elements.searchInput.value.toLowerCase();
    renderLogs();
  }
  
  // Control functions
  function toggleAutoScroll() {
    CONFIG.autoScroll = !CONFIG.autoScroll;
    
    const btn = elements.autoScrollBtn;
    const icon = btn.querySelector('.icon');
    
    if (CONFIG.autoScroll) {
      btn.innerHTML = '<span class="icon">📌</span> Auto-scroll: ON';
      btn.classList.add('active');
      elements.logBox.scrollTop = elements.logBox.scrollHeight;
    } else {
      btn.innerHTML = '<span class="icon">📍</span> Auto-scroll: OFF';
      btn.classList.remove('active');
    }
  }
  
  function togglePause() {
    CONFIG.isPaused = !CONFIG.isPaused;
    
    const btn = elements.pauseBtn;
    
    if (CONFIG.isPaused) {
      btn.innerHTML = '<span class="icon">▶️</span> Resume';
      btn.classList.add('active');
      clearInterval(refreshTimer);
      updateConnectionStatus('paused');
    } else {
      btn.innerHTML = '<span class="icon">⏸️</span> Pause';
      btn.classList.remove('active');
      startLogFetching();
      updateConnectionStatus('connected');
    }
  }
  
  async function clearLogs() {
    // Update confirmation message to be more accurate
    if (confirm('Are you sure you want to clear the logs on the server? This will back up the current log file and start a new one.')) {
      try {
        // You might want to show a loading indicator here
        updateConnectionStatus('connecting'); // Indicate activity
  
        const response = await fetch('/api/clear-logs', {
          method: 'POST',
          headers: {
            // Session cookies are typically sent automatically by the browser.
            // If you have CSRF tokens or other specific headers, add them here.
            'Content-Type': 'application/json' // Good practice, though no body is sent for this specific request
          }
        });
  
        const data = await response.json(); // The server sends back JSON
  
        if (response.ok && data.status === 'success') {
          showNotification(data.message + (data.backup_file ? ` Backup: ${data.backup_file}` : ''), 'success');
          // Fetch logs again to show the current state from the server.
          // fetchLogs() will update the logCache, stats, and re-render.
          await fetchLogs();
        } else {
          const errorMessage = data.error || 'Failed to clear logs on the server.';
          console.error('Failed to clear logs:', errorMessage);
          showNotification(errorMessage, 'error');
          updateConnectionStatus('connected'); // Revert status if failed
        }
      } catch (error) {
        console.error('Error clearing logs:', error);
        showNotification('An error occurred while trying to clear logs: ' + error.message, 'error');
        updateConnectionStatus('disconnected'); // Show disconnection on network error
      }
    }
  }
  
  // Download functionality
  async function downloadLogs() {
    try {
      const response = await fetch('/logs');
      const data = await response.json();
      
      if (data && data.logs) {
        const blob = new Blob([data.logs], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `detection-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
        a.style.display = 'none';
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        window.URL.revokeObjectURL(url);
        
        // Show success feedback
        showNotification('Logs downloaded successfully!', 'success');
      }
    } catch (error) {
      console.error('Download error:', error);
      showNotification('Failed to download logs', 'error');
    }
  }
  
  // Connection status management
  function updateConnectionStatus(status) {
    if (!elements.statusDot || !elements.statusText) return;
    
    elements.statusDot.className = 'status-dot';
    
    switch (status) {
      case 'connected':
        elements.statusText.textContent = 'Connected';
        break;
      case 'connecting':
        elements.statusText.textContent = 'Connecting...';
        break;
      case 'disconnected':
        elements.statusDot.classList.add('disconnected');
        elements.statusText.textContent = 'Disconnected';
        break;
      case 'paused':
        elements.statusText.textContent = 'Paused';
        break;
    }
  }
  
  // Error display
  function displayError(message) {
    if (!elements.logBox) return;
    
    elements.logBox.innerHTML = `
      <div class="log-line alert">
        <strong>Connection Error:</strong> ${message}
      </div>
      <div class="log-line info">
        Retrying in ${CONFIG.refreshInterval / 1000} seconds...
      </div>
    `;
  }
  
  // Notification system
  function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      background: ${type === 'success' ? '#27ae60' : '#e74c3c'};
      color: white;
      border-radius: 6px;
      z-index: 1000;
      animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
  
  // Timer management
  function startLogFetching() {
    clearInterval(refreshTimer);
    
    // Initial fetch
    fetchLogs();
    
    // Set up recurring fetches
    refreshTimer = setInterval(fetchLogs, CONFIG.refreshInterval);
  }
  
  function pauseRefreshing() {
    clearInterval(refreshTimer);
  }
  
  function resumeRefreshing() {
    if (!CONFIG.isPaused) {
      startLogFetching();
    }
  }
  
  // Utility functions
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    }};