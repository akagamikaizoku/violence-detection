// DOM elements
const loginForm = document.getElementById('loginForm');
const loginButton = document.getElementById('loginButton');
const togglePasswordBtn = document.getElementById('togglePassword');
const passwordInput = document.getElementById('password');
const usernameInput = document.getElementById('username');
const errorMessage = document.getElementById('errorMessage');
const buttonText = loginButton.querySelector('.button-text');
const buttonLoader = loginButton.querySelector('.button-loader');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeEventListeners();
    initializeAnimations();
    initializeAccessibility();
    initializeAdvancedFeatures(); // Keep this call, but password strength is removed from it
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

// Event listeners
function initializeEventListeners() {
    // Password toggle functionality
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', togglePasswordVisibility);
    }

    // Form submission with loading state
    if (loginForm) {
        loginForm.addEventListener('submit', handleFormSubmission);
    }

    // Real-time validation
    if (usernameInput) {
        usernameInput.addEventListener('input', validateUsername);
        usernameInput.addEventListener('blur', validateUsername);
    }

    if (passwordInput) {
        passwordInput.addEventListener('input', validatePassword);
        passwordInput.addEventListener('blur', validatePassword);
    }

    // Auto-dismiss error messages
    if (errorMessage) {
        setTimeout(() => {
            dismissErrorMessage();
        }, 5000);
    }

    // Remember me functionality
    const rememberMeCheckbox = document.getElementById('rememberMe');
    if (rememberMeCheckbox) {
        // Load saved username if remember me was checked
        loadSavedCredentials();
        rememberMeCheckbox.addEventListener('change', handleRememberMeChange);
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// Password visibility toggle
function togglePasswordVisibility() {
    const eyeOpen = togglePasswordBtn.querySelector('.eye-open');
    const eyeClosed = togglePasswordBtn.querySelector('.eye-closed');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeOpen.style.display = 'none';
        eyeClosed.style.display = 'block';
        passwordInput.focus();
    } else {
        passwordInput.type = 'password';
        eyeOpen.style.display = 'block';
        eyeClosed.style.display = 'none';
        passwordInput.focus();
    }
}

// Form submission handler
function handleFormSubmission(e) {
    // Show loading state
    showLoadingState();

    // Save credentials if remember me is checked
    const rememberMe = document.getElementById('rememberMe');
    if (rememberMe && rememberMe.checked) {
        saveCredentials();
    }

    // Add a small delay to show the loading animation
    // The actual form will still submit normally to Flask
    setTimeout(() => {
        // Form will submit naturally, this just enhances the UX
    }, 300);
}

// Loading state management
function showLoadingState() {
    loginButton.disabled = true;
    buttonText.style.display = 'none';
    buttonLoader.style.display = 'flex';
    loginButton.style.cursor = 'not-allowed';
}

function hideLoadingState() {
    loginButton.disabled = false;
    buttonText.style.display = 'block';
    buttonLoader.style.display = 'none';
    loginButton.style.cursor = 'pointer';
}

// Input validation
function validateUsername() {
    const username = usernameInput.value.trim();
    const inputWrapper = usernameInput.closest('.input-wrapper');

    if (username.length > 0 && username.length < 3) {
        addInputError(inputWrapper, 'Username must be at least 3 characters');
        return false;
    } else {
        removeInputError(inputWrapper);
        return true;
    }
}

function validatePassword() {
    const password = passwordInput.value;
    const inputWrapper = passwordInput.closest('.input-wrapper');

    if (password.length > 0 && password.length < 6) {
        addInputError(inputWrapper, 'Password must be at least 6 characters');
        return false;
    } else {
        removeInputError(inputWrapper);
        return true;
    }
}

function addInputError(inputWrapper, message) {
    const input = inputWrapper.querySelector('input');
    input.style.borderColor = '#e53e3e';
    input.style.boxShadow = '0 0 0 3px rgba(229, 62, 62, 0.1)';

    // Remove existing error message
    const existingError = inputWrapper.parentNode.querySelector('.input-error');
    if (existingError) {
        existingError.remove();
    }

    // Add new error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'input-error';
    errorDiv.style.cssText = `
        color: #e53e3e;
        font-size: 12px;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 4px;
    `;
    errorDiv.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        ${message}
    `;

    inputWrapper.parentNode.appendChild(errorDiv);
}

function removeInputError(inputWrapper) {
    const input = inputWrapper.querySelector('input');
    input.style.borderColor = '#e2e8f0'; // Default border color
    input.style.boxShadow = '';

    const errorDiv = inputWrapper.parentNode.querySelector('.input-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// Remember me functionality
function handleRememberMeChange() {
    const rememberMe = document.getElementById('rememberMe');
    if (!rememberMe.checked) {
        // Clear saved credentials
        sessionStorage.removeItem('savedUsername');
    }
}

function saveCredentials() {
    const username = usernameInput.value.trim();
    if (username) {
        sessionStorage.setItem('savedUsername', username);
    }
}

function loadSavedCredentials() {
    const savedUsername = sessionStorage.getItem('savedUsername');
    if (savedUsername && usernameInput) {
        usernameInput.value = savedUsername;
        document.getElementById('rememberMe').checked = true;
    }
}

// Error message management
function dismissErrorMessage() {
    if (errorMessage) {
        errorMessage.style.opacity = '0';
        errorMessage.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 300);
    }
}

// Keyboard shortcuts
function handleKeyboardShortcuts(e) {
    // Alt + P to focus password field
    if (e.altKey && e.key === 'p') {
        e.preventDefault();
        passwordInput.focus();
    }

    // Alt + U to focus username field
    if (e.altKey && e.key === 'u') {
        e.preventDefault();
        usernameInput.focus();
    }

    // Escape to clear form
    if (e.key === 'Escape') {
        clearForm();
    }
}

function clearForm() {
    usernameInput.value = '';
    passwordInput.value = '';
    document.getElementById('rememberMe').checked = false;
    removeInputError(usernameInput.closest('.input-wrapper'));
    removeInputError(passwordInput.closest('.input-wrapper'));
    usernameInput.focus();
}

// Animations and visual effects
function initializeAnimations() {
    // Add smooth focus transitions
    const inputs = document.querySelectorAll('input[type="text"], input[type="password"]');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentNode.style.transform = 'scale(1.02)';
            this.parentNode.style.transition = 'transform 0.2s ease';
        });

        input.addEventListener('blur', function() {
            this.parentNode.style.transform = 'scale(1)';
        });
    });

    // Add ripple effect to button
    loginButton.addEventListener('click', createRippleEffect);

    // Animate form elements on load
    animateFormElements();
}

function createRippleEffect(e) {
    const button = e.currentTarget;
    const rect = button.getBoundingClientRect();
    const ripple = document.createElement('span');
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    ripple.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
        background: rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        transform: scale(0);
        animation: ripple 0.6s linear;
        pointer-events: none;
    `;

    button.appendChild(ripple);

    setTimeout(() => {
        ripple.remove();
    }, 600);
}

function animateFormElements() {
    const formGroups = document.querySelectorAll('.form-group');
    formGroups.forEach((group, index) => {
        group.style.opacity = '0';
        group.style.transform = 'translateY(20px)';
        group.style.transition = 'all 0.4s ease';

        setTimeout(() => {
            group.style.opacity = '1';
            group.style.transform = 'translateY(0)';
        }, 200 + index * 100);
    });
}

// Accessibility enhancements
function initializeAccessibility() {
    // Add ARIA labels
    usernameInput.setAttribute('aria-describedby', 'username-help');
    passwordInput.setAttribute('aria-describedby', 'password-help');

    // Add screen reader announcements for dynamic changes
    const srAnnouncer = document.createElement('div');
    srAnnouncer.setAttribute('aria-live', 'polite');
    srAnnouncer.setAttribute('aria-atomic', 'true');
    srAnnouncer.style.cssText = `
        position: absolute;
        left: -10000px;
        top: auto;
        width: 1px;
        height: 1px;
        overflow: hidden;
    `;
    document.body.appendChild(srAnnouncer);

    // Announce loading state
    window.announceToScreenReader = function(message) {
        srAnnouncer.textContent = message;
        setTimeout(() => {
            srAnnouncer.textContent = '';
        }, 1000);
    };

    // Announce when form is submitted
    loginForm.addEventListener('submit', () => {
        announceToScreenReader('Signing in, please wait...');
    });
}

// Additional CSS animations via JavaScript
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }

    .input-wrapper {
        transition: transform 0.2s ease;
    }

    .form-group {
        transition: all 0.4s ease;
    }

    .error-message {
        transition: opacity 0.3s ease, transform 0.3s ease;
    }

    /* Enhanced hover effects */
    .login-card:hover {
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
    }

    /* Smooth transitions for all interactive elements */
    .checkbox-container:hover .checkmark {
        border-color: #26D0CE; /* New Theme: Accent color */
        transform: scale(1.1);
    }

    .forgot-password:hover {
        transform: translateY(-1px); /* color change handled in CSS */
    }

    /* signup-link removed */

    /* Loading state enhancements */
    .login-button.loading { /* This class isn't explicitly added in the JS, but keeping style if it were */
        background: linear-gradient(135deg, #9CA3AF 0%, #E5E7EB 100%);
    }

    /* Focus enhancements (already handled in main CSS, but keep for consistency if needed) */
    .input-wrapper input:focus {
        transform: translateY(-1px);
    }

    /* Mobile touch enhancements */
    @media (hover: none) and (pointer: coarse) {
        .login-button:active {
            transform: scale(0.98);
        }

        .toggle-password:active {
            transform: scale(0.95);
        }

        .checkbox-container:active .checkmark {
            transform: scale(0.95);
        }
    }
`;
document.head.appendChild(style);

// Advanced features (Password strength checker removed from here)
function initializeAdvancedFeatures() {
    /*
    // Auto-capitalize first letter of username
    if (usernameInput) {
        usernameInput.addEventListener('input', function(e) {
            const value = e.target.value;
            if (value.length === 1) {
                // Only attempt to uppercase if it's a letter
                if (value.match(/[a-zA-Z]/i)) {
                    e.target.value = value.charAt(0).toUpperCase();
                }
            }
        });
    }
    */

    document.addEventListener('keydown', function(e) {
        if (typeof e.getModifierState === 'function' && e.getModifierState('CapsLock')) {
            showCapsLockWarning();
        } else {
            hideCapsLockWarning();
        }
    });

    // Auto-focus next field on Enter
    if (usernameInput && passwordInput) {
        usernameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                passwordInput.focus();
            }
        });
    }
}


function showCapsLockWarning() {
    const existingWarning = document.querySelector('.caps-lock-warning');
    if (existingWarning) return;

    const warning = document.createElement('div');
    warning.className = 'caps-lock-warning';
    warning.style.cssText = `
        background: #fed7d7; /* Orange/yellow might be better: #FFF3CD; color: #664D03; */
        color: #c53030;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
        margin-top: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
        animation: slideDown 0.3s ease;
    `;
    warning.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        Caps Lock is on
    `;

    const passwordGroup = passwordInput.closest('.form-group');
    if (passwordGroup) { // Ensure passwordGroup is found
        passwordGroup.appendChild(warning);
    }
}

function hideCapsLockWarning() {
    const warning = document.querySelector('.caps-lock-warning');
    if (warning) {
        // A simple removal might be better than slideUp animation if it causes layout shifts
        warning.remove();
    }
}

// Password strength indicator functions (updatePasswordStrength, createPasswordStrengthIndicator) are REMOVED.

// Handle form reset
function resetForm() {
    if (loginForm) {
        loginForm.reset();
    }
    hideLoadingState();
    if (usernameInput) removeInputError(usernameInput.closest('.input-wrapper'));
    if (passwordInput) removeInputError(passwordInput.closest('.input-wrapper'));
    hideCapsLockWarning();
    // Password strength indicator cleanup is REMOVED.
}

// Export functions for potential external use
window.LoginForm = {
    showLoadingState,
    hideLoadingState,
    resetForm,
    validateForm: function() {
        const isUsernameValid = usernameInput ? validateUsername() : true;
        const isPasswordValid = passwordInput ? validatePassword() : true;
        return isUsernameValid && isPasswordValid;
    }
};