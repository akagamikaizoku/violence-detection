// Utility Functions for Enhanced UX

// Notification System
class NotificationManager {
  constructor() {
    this.notifications = [];
    this.maxNotifications = 3;
  }

  show(message, type = 'info', title = '', duration = 4000) {
    const notification = this.createNotification(message, type, title);
    document.body.appendChild(notification);
    this.notifications.push(notification);

    // Position notifications
    this.repositionNotifications();

    // Auto dismiss
    setTimeout(() => {
      this.dismiss(notification);
    }, duration);

    // Add close button functionality
    const closeBtn = notification.querySelector('.notification-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.dismiss(notification));
    }

    // Remove oldest if too many
    if (this.notifications.length > this.maxNotifications) {
      this.dismiss(this.notifications[0]);
    }

    return notification;
  }

  createNotification(message, type, title) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    
    const icons = {
      success: 'fa-check-circle',
      error: 'fa-times-circle',
      warning: 'fa-exclamation-triangle',
      info: 'fa-info-circle'
    };

    const titles = {
      success: title || 'Success',
      error: title || 'Error',
      warning: title || 'Warning',
      info: title || 'Info'
    };

    notification.innerHTML = `
      <i class="fas ${icons[type] || icons.info}"></i>
      <div class="notification-content">
        <div class="notification-title">${titles[type]}</div>
        <div class="notification-message">${message}</div>
      </div>
      <button class="notification-close">
        <i class="fas fa-times"></i>
      </button>
    `;

    return notification;
  }

  dismiss(notification) {
    if (!notification || !notification.parentNode) return;
    
    notification.style.animation = 'notificationSlide 0.3s ease-out reverse';
    setTimeout(() => {
      notification.remove();
      this.notifications = this.notifications.filter(n => n !== notification);
      this.repositionNotifications();
    }, 300);
  }

  repositionNotifications() {
    this.notifications.forEach((notification, index) => {
      notification.style.top = `${80 + (index * 90)}px`;
    });
  }
}

// Create global notification manager
const notify = new NotificationManager();

// Smooth Scroll
function smoothScrollTo(element, duration = 500) {
  const target = typeof element === 'string' ? document.querySelector(element) : element;
  if (!target) return;

  const targetPosition = target.getBoundingClientRect().top + window.pageYOffset;
  const startPosition = window.pageYOffset;
  const distance = targetPosition - startPosition;
  let startTime = null;

  function animation(currentTime) {
    if (startTime === null) startTime = currentTime;
    const timeElapsed = currentTime - startTime;
    const run = ease(timeElapsed, startPosition, distance, duration);
    window.scrollTo(0, run);
    if (timeElapsed < duration) requestAnimationFrame(animation);
  }

  function ease(t, b, c, d) {
    t /= d / 2;
    if (t < 1) return c / 2 * t * t + b;
    t--;
    return -c / 2 * (t * (t - 2) - 1) + b;
  }

  requestAnimationFrame(animation);
}

// Copy to Clipboard
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    notify.show('Copied to clipboard!', 'success');
    return true;
  } catch (err) {
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
      notify.show('Copied to clipboard!', 'success');
      return true;
    } catch (err) {
      notify.show('Failed to copy', 'error');
      return false;
    } finally {
      document.body.removeChild(textArea);
    }
  }
}

// Format Date/Time
function formatDateTime(date, format = 'full') {
  const d = new Date(date);
  
  const formats = {
    full: d.toLocaleString(),
    date: d.toLocaleDateString(),
    time: d.toLocaleTimeString(),
    short: d.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    }),
    iso: d.toISOString()
  };

  return formats[format] || formats.full;
}

// Debounce Function
function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Throttle Function
function throttle(func, limit = 300) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// Local Storage Helper
const storage = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      console.error('Storage error:', e);
      return false;
    }
  },
  
  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
      console.error('Storage error:', e);
      return defaultValue;
    }
  },
  
  remove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (e) {
      console.error('Storage error:', e);
      return false;
    }
  },
  
  clear() {
    try {
      localStorage.clear();
      return true;
    } catch (e) {
      console.error('Storage error:', e);
      return false;
    }
  }
};

// Loading Spinner
function showLoading(message = 'Loading...') {
  const loading = document.createElement('div');
  loading.id = 'global-loading';
  loading.innerHTML = `
    <div style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      backdrop-filter: blur(4px);
    ">
      <div style="
        background: white;
        padding: 30px 40px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
      ">
        <div class="spinner" style="
          width: 50px;
          height: 50px;
          border: 4px solid #f3f3f3;
          border-top: 4px solid #667eea;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 20px;
        "></div>
        <p style="
          font-size: 16px;
          color: #2c3e50;
          font-weight: 600;
          margin: 0;
        ">${message}</p>
      </div>
    </div>
  `;
  document.body.appendChild(loading);
}

function hideLoading() {
  const loading = document.getElementById('global-loading');
  if (loading) loading.remove();
}

// Confirm Dialog
function confirm(message, onConfirm, onCancel) {
  const dialog = document.createElement('div');
  dialog.innerHTML = `
    <div style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      backdrop-filter: blur(4px);
    ">
      <div style="
        background: white;
        padding: 30px;
        border-radius: 16px;
        max-width: 400px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
      ">
        <p style="
          font-size: 16px;
          color: #2c3e50;
          margin-bottom: 25px;
          line-height: 1.6;
        ">${message}</p>
        <div style="
          display: flex;
          gap: 10px;
          justify-content: flex-end;
        ">
          <button class="cancel-btn" style="
            padding: 10px 20px;
            border: 2px solid #95a5a6;
            background: white;
            color: #2c3e50;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
          ">Cancel</button>
          <button class="confirm-btn" style="
            padding: 10px 20px;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
          ">Confirm</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(dialog);

  dialog.querySelector('.confirm-btn').addEventListener('click', () => {
    if (onConfirm) onConfirm();
    dialog.remove();
  });

  dialog.querySelector('.cancel-btn').addEventListener('click', () => {
    if (onCancel) onCancel();
    dialog.remove();
  });
}

// Export utilities
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    notify,
    smoothScrollTo,
    copyToClipboard,
    formatDateTime,
    debounce,
    throttle,
    storage,
    showLoading,
    hideLoading,
    confirm
  };
}
