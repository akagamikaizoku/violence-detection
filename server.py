from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, disconnect
import os
import json
import logging
from datetime import datetime, timedelta
import threading
import time
from functools import wraps
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate secure random key
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
CONFIG = {
    'LOG_FILE': 'detection_logs.log',
    'USERNAME': 'admin',
    'PASSWORD': 'password123',  # Change this in production!
    'MAX_LOG_SIZE': 10 * 1024 * 1024,  # 10MB
    'LOG_RETENTION_DAYS': 30,
    'SESSION_TIMEOUT': 3600,  # 1 hour
    'RATE_LIMIT_WINDOW': 60,  # Default 1 minute for general rate limits
    'RATE_LIMIT_MAX': 100,     # Default Max requests per window for general rate limits
    'DETECT_RATE_LIMIT_MAX': 200,  # Max requests for /detect endpoint (increased)
    'DETECT_RATE_LIMIT_WINDOW': 60 # Window for /detect endpoint rate limit
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rate limiting storage
rate_limit_storage = {}

# Active WebSocket connections
active_connections = []

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized', 'redirect': '/login'}), 401
            return redirect(url_for('login'))
        
        # Check session timeout
        if 'login_time' in session:
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(seconds=CONFIG['SESSION_TIMEOUT']):
                session.clear()
                if request.is_json:
                    return jsonify({'error': 'Session expired', 'redirect': '/login'}), 401
                return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(max_requests=None, window=None): # Changed default to None
    """Rate limiting decorator"""
    # Use general config defaults if specific values are not provided
    max_requests_default = CONFIG.get('RATE_LIMIT_MAX', 100)
    window_default = CONFIG.get('RATE_LIMIT_WINDOW', 60)

    final_max_requests = max_requests if max_requests is not None else max_requests_default
    final_window = window if window is not None else window_default
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            current_time = time.time()
            
            # Clean old entries
            cutoff_time = current_time - final_window
            if client_ip in rate_limit_storage:
                rate_limit_storage[client_ip] = [
                    timestamp for timestamp in rate_limit_storage[client_ip] 
                    if timestamp > cutoff_time
                ]
            else:
                rate_limit_storage[client_ip] = []
            
            # Check rate limit
            if len(rate_limit_storage[client_ip]) >= final_max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip} on endpoint: {request.endpoint}. Limit: {final_max_requests}/{final_window}s")
                # Try to get retry_after from the specific error if available, else use window
                retry_val = getattr(request, 'retry_after', final_window)
                return jsonify({'error': 'Rate limit exceeded', 'retry_after': retry_val }), 429
            
            # Add current request
            rate_limit_storage[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_log_entry(level, message, source="SYSTEM", extra_data=None):
    """Create a standardized log entry"""
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'level': level.upper(),
        'source': source,
        'message': message
    }
    
    if extra_data:
        log_entry.update(extra_data)
    
    # Format for file storage
    log_line = f"[{timestamp}] [{level.upper()}] [{source}] {message}"
    if extra_data:
        log_line += f" | Data: {json.dumps(extra_data, separators=(',', ':'))}"
    
    return log_line + "\n", log_entry

def write_log(log_line, broadcast=True):
    """Write log to file and optionally broadcast to WebSocket clients"""
    try:
        # Check log file size and rotate if necessary
        if os.path.exists(CONFIG['LOG_FILE']):
            if os.path.getsize(CONFIG['LOG_FILE']) > CONFIG['MAX_LOG_SIZE']:
                rotate_log_file()
        
        # Write to file
        with open(CONFIG['LOG_FILE'], 'a', encoding='utf-8') as f:
            f.write(log_line)
        
        # Broadcast to WebSocket clients
        if broadcast and active_connections:
            socketio.emit('new_log', {
                'type': 'log',
                'log': log_line.strip()
            }, namespace='/logs')
            
    except Exception as e:
        logger.error(f"Error writing log: {e}")

def rotate_log_file():
    """Rotate log file when it gets too large"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{CONFIG['LOG_FILE']}.{timestamp}"
        os.rename(CONFIG['LOG_FILE'], backup_filename)
        logger.info(f"Log file rotated to {backup_filename}")
        
        # Clean old log files
        cleanup_old_logs()
        
    except Exception as e:
        logger.error(f"Error rotating log file: {e}")

def cleanup_old_logs():
    """Clean up old log files based on retention policy"""
    try:
        current_time = time.time()
        retention_seconds = CONFIG['LOG_RETENTION_DAYS'] * 24 * 3600
        
        for filename in os.listdir('.'):
            if filename.startswith(CONFIG['LOG_FILE'] + '.'):
                file_path = os.path.join('.', filename)
                if os.path.getctime(file_path) < current_time - retention_seconds:
                    os.remove(file_path)
                    logger.info(f"Removed old log file: {filename}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}")

def hash_password(password):
    """Hash password for secure storage"""
    # Note: A static salt is used here for simplicity. In a real production system,
    # use a unique salt per user and store it with the hash.
    # Also, PBKDF2 iteration count should be as high as feasible.
    salt = b'static_salt_for_pbkdf2_example' # Example salt, should be randomly generated and stored per user in prod
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()

def clear_rate_limit_for_ip(ip):
    """Clear rate limit for specific IP (utility function)"""
    if ip in rate_limit_storage:
        del rate_limit_storage[ip]
        logger.info(f"Cleared rate limit for IP: {ip}")

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        current_time = time.time()
        
        login_key = f"login_{client_ip}"
        login_window = 300  # 5 minutes for login attempts
        max_login_attempts = 10 # Max login attempts
        
        cutoff_time = current_time - login_window
        if login_key in rate_limit_storage:
            rate_limit_storage[login_key] = [
                timestamp for timestamp in rate_limit_storage[login_key] 
                if timestamp > cutoff_time
            ]
        else:
            rate_limit_storage[login_key] = []
        
        if len(rate_limit_storage[login_key]) >= max_login_attempts:
            logger.warning(f"Login rate limit exceeded for IP: {client_ip}")
            # Set retry_after on the request object for the error handler
            setattr(request, 'retry_after', login_window - (current_time - rate_limit_storage[login_key][0]) if rate_limit_storage[login_key] else login_window)
            return render_template('login.html', error=f'Too many login attempts. Please try again in {int(getattr(request, "retry_after", login_window)/60)} minutes.')
        
        rate_limit_storage[login_key].append(current_time)
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            logger.warning(f"Login attempt with empty credentials from {request.remote_addr}")
            return render_template('login.html', error='Please enter both username and password')
        
        # For simplicity, comparing plain text password from config.
        # In production, hash the input password and compare with a stored hash.
        # e.g. if CONFIG['PASSWORD_HASH'] == hash_password(password):
        if username == CONFIG['USERNAME'] and password == CONFIG['PASSWORD']: # Direct comparison for this example
            session['username'] = username
            session['login_time'] = datetime.now().isoformat()
            
            clear_rate_limit_for_ip(client_ip) # Clear general rate limit for the IP
            if login_key in rate_limit_storage: # Clear login specific rate limit
                del rate_limit_storage[login_key]
            
            log_line, _ = create_log_entry('INFO', f'User {username} logged in successfully', 'AUTH',
                                           {'ip': request.remote_addr, 'user_agent': request.user_agent.string})
            write_log(log_line)
            logger.info(f"Successful login for user: {username} from {request.remote_addr}")
            return redirect(url_for('dashboard'))
        else:
            log_line, _ = create_log_entry('WARNING', f'Failed login attempt for user: {username}', 'AUTH',
                                           {'ip': request.remote_addr, 'user_agent': request.user_agent.string})
            write_log(log_line)
            logger.warning(f"Failed login attempt for user: {username} from {request.remote_addr}")
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/dashboard')
@require_auth
def dashboard():
    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    log_line, _ = create_log_entry('INFO', f'User {username} logged out', 'AUTH', {'ip': request.remote_addr})
    write_log(log_line)
    session.clear()
    logger.info(f"User {username} logged out from {request.remote_addr}")
    return redirect(url_for('login'))

@app.route('/logs')
@require_auth
@rate_limit(max_requests=30, window=60) # Specific rate limit for logs endpoint
def get_logs():
    try:
        if not os.path.exists(CONFIG['LOG_FILE']):
            with open(CONFIG['LOG_FILE'], 'w', encoding='utf-8') as f: # Ensure utf-8 encoding
                log_line, _ = create_log_entry('INFO', 'Log file initialized', 'SYSTEM')
                f.write(log_line)
            return jsonify({'logs': 'Log file initialized. No logs available yet.'})
        
        try:
            with open(CONFIG['LOG_FILE'], 'r', encoding='utf-8') as file:
                all_lines = file.readlines()

            login_time = datetime.fromisoformat(session['login_time'])
            filtered_lines = []
            for line in all_lines:
                try:
                    # Example: [2023-10-27T10:00:00.123456] [INFO] ...
                    ts_str = line.split(']')[0].strip('[')
                    log_time = datetime.fromisoformat(ts_str)
                    if log_time >= login_time:
                        filtered_lines.append(line)
                except Exception:
                    continue  # Skip lines with format issues
            logs = ''.join(filtered_lines)
        except UnicodeDecodeError: # Fallback for potential encoding issues if file was created differently
            with open(CONFIG['LOG_FILE'], 'r', encoding='latin-1') as file:
                logs = file.read()
        
        lines = logs.split('\n')
        if len(lines) > 1000: # Limit to last 1000 lines for performance
            logs = '\n'.join(lines[-1000:])
        
        return jsonify({'logs': logs, 'total_lines': len(lines)})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({'error': 'Failed to read logs', 'details': str(e)}), 500

@app.route('/detect', methods=['POST'])
@rate_limit(max_requests=CONFIG['DETECT_RATE_LIMIT_MAX'], window=CONFIG['DETECT_RATE_LIMIT_WINDOW'])
def detect():
    try:
        if request.is_json:
            data = request.get_json(force=True) # force=True can be risky if content-type is not strictly application/json
        else:
            data = request.form.to_dict()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        detection_type = data.get('type', 'UNKNOWN')
        severity = data.get('severity', 'MEDIUM').upper() # Standardize severity
        message = data.get('message', 'Detection event occurred')
        source_ip = data.get('source_ip', request.remote_addr)
        
        log_level = 'ALERT' if severity in ['HIGH', 'CRITICAL'] else 'WARNING'
        
        log_line, log_entry = create_log_entry(
            log_level,
            f'Detection: {message}',
            'DETECTION',
            {
                'detection_type': detection_type,
                'severity': severity,
                'source_ip': source_ip,
                'user_agent': request.user_agent.string,
                'raw_data': data # Be cautious logging raw_data if it can be very large or sensitive
            }
        )
        write_log(log_line, broadcast=True)
        logger.info(f"Detection logged: {detection_type} ({severity}) from {source_ip}")
        
        return jsonify({
            'message': 'Detection logged successfully',
            'log_entry': log_entry, # Consider if returning full log_entry is needed by client
            'status': 'success'
        })
    except json.JSONDecodeError as e:
        error_msg = f'Invalid JSON data format: {str(e)}'
        logger.error(f"JSON decode error in /detect: {error_msg} from {request.remote_addr}")
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        error_msg = f'Error processing detection: {str(e)}'
        logger.error(f"Error in /detect: {e}", exc_info=True) # Add exc_info for better debugging
        return jsonify({'error': error_msg}), 500

@app.route('/api/stats')
@require_auth
@rate_limit() # Uses default rate limits from CONFIG
def get_stats():
    try:
        if not os.path.exists(CONFIG['LOG_FILE']):
            return jsonify({'error': 'No logs available'}), 404
        
        stats = {'total': 0, 'alert': 0, 'warning': 0, 'info': 0, 'error': 0, 'debug': 0}
        # Improved parsing to be more robust
        with open(CONFIG['LOG_FILE'], 'r', encoding='utf-8') as file:
            for line in file:
                line_stripped = line.strip()
                if not line_stripped: continue
                stats['total'] += 1
                # Example: [2023-10-27T10:00:00.123456] [LEVEL] ...
                try:
                    level_part = line_stripped.split('] [', 2)[1].split(']')[0].upper()
                    if level_part in ['ALERT', 'CRITICAL']: stats['alert'] += 1
                    elif level_part in ['WARNING', 'WARN']: stats['warning'] += 1
                    elif level_part in ['ERROR', 'FATAL']: stats['error'] += 1
                    elif level_part == 'DEBUG': stats['debug'] += 1
                    elif level_part == 'INFO': stats['info'] += 1
                    else: # Fallback for lines that might not match perfectly
                        if '[ALERT]' in line_stripped.upper() or '[CRITICAL]' in line_stripped.upper(): stats['alert'] +=1
                        elif '[WARNING]' in line_stripped.upper() or '[WARN]' in line_stripped.upper(): stats['warning'] += 1
                        elif '[ERROR]' in line_stripped.upper() or '[FATAL]' in line_stripped.upper(): stats['error'] += 1
                        elif '[DEBUG]' in line_stripped.upper(): stats['debug'] += 1
                        else: stats['info'] +=1 # Default to info if no other level found
                except IndexError: # If line format is unexpected
                    stats['info'] += 1 # Default to info
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get statistics'}), 500

@app.route('/api/clear-logs', methods=['POST'])
@require_auth
@rate_limit(max_requests=5, window=300) # Stricter limit for admin actions
def clear_logs():
    try:
        username = session.get('username')
        backup_file_path = None # Initialize
        if os.path.exists(CONFIG['LOG_FILE']):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file_path = f"{CONFIG['LOG_FILE']}.cleared.{timestamp}"
            os.rename(CONFIG['LOG_FILE'], backup_file_path)
        
        log_line, _ = create_log_entry('INFO', f'Logs cleared by user {username}', 'ADMIN',
                                       {'backup_file': backup_file_path})
        write_log(log_line) # This creates a new log file with the clear action
        logger.info(f"Logs cleared by user: {username}. Backup: {backup_file_path or 'N/A'}")
        return jsonify({'message': 'Logs cleared successfully', 'status': 'success', 'backup_file': backup_file_path})
    except Exception as e:
        logger.error(f"Error clearing logs: {e}", exc_info=True)
        return jsonify({'error': 'Failed to clear logs'}), 500

@app.route('/api/clear-rate-limits', methods=['POST'])
@require_auth
@rate_limit(max_requests=5, window=300) # Stricter limit
def clear_rate_limits():
    try:
        rate_limit_storage.clear()
        logger.info(f"All rate limits cleared by admin: {session.get('username')}")
        return jsonify({'message': 'Rate limits cleared successfully', 'status': 'success'})
    except Exception as e:
        logger.error(f"Error clearing rate limits: {e}", exc_info=True)
        return jsonify({'error': 'Failed to clear rate limits'}), 500

# WebSocket events
@socketio.on('connect', namespace='/logs')
def handle_connect():
    if 'username' not in session: # Authenticate WebSocket connections
        logger.warning(f"Unauthorized WebSocket connection attempt from {request.sid}")
        disconnect()
        return False # Explicitly deny connection
    
    active_connections.append(request.sid)
    logger.info(f"WebSocket client connected: {request.sid} (User: {session.get('username')})")
    emit('status', {'message': 'Connected to log stream'})
    return True # Explicitly allow connection

@socketio.on('disconnect', namespace='/logs')
def handle_disconnect():
    if request.sid in active_connections:
        active_connections.remove(request.sid)
    logger.info(f"WebSocket client disconnected: {request.sid} (User: {session.get('username', 'N/A')})")

@socketio.on('subscribe', namespace='/logs')
@require_auth # Use decorator for socket events if possible, or manual check
def handle_subscribe(data):
    # Redundant check if @require_auth worked, but good for direct socket event auth
    if 'username' not in session:
        disconnect()
        return
    emit('status', {'message': 'Subscribed to log updates'}) # Send to specific client
    logger.info(f"Client {request.sid} (User: {session.get('username')}) subscribed to log updates with data: {data}")


# Error handlers
@app.errorhandler(404)
def not_found(error):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}", exc_info=True)
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({'error': 'Internal server error', 'details': str(error)}), 500
    return render_template('500.html'), 500

@app.errorhandler(429)
def rate_limit_handler(error):
    # The 'retry_after' value might have been set on the request object by the rate_limit decorator or login handler
    retry_after_value = getattr(request, 'retry_after', CONFIG.get('RATE_LIMIT_WINDOW', 60))
    logger.warning(f"Rate limit triggered for {request.remote_addr} on {request.path}. Retry after: {retry_after_value}s")
    return jsonify({
        'error': 'Rate limit exceeded. Please try again later.',
        'message': 'Too many requests from your IP address.',
        'retry_after': int(retry_after_value) # Ensure it's an int
    }), 429

# Background task for log monitoring
def log_monitor():
    """Background task to monitor system health and perform cleanup"""
    logger.info("Log monitor thread started.")
    while True:
        try:
            # Check disk space (log file size monitoring)
            if os.path.exists(CONFIG['LOG_FILE']):
                file_size = os.path.getsize(CONFIG['LOG_FILE'])
                if file_size > CONFIG['MAX_LOG_SIZE'] * 0.9:  # 90% of max size
                    log_line, _ = create_log_entry('WARNING', f'Log file approaching size limit: {file_size / (1024*1024):.2f}MB', 'MONITOR')
                    write_log(log_line)
            
            # Clean old rate limiting entries periodically (more robustly)
            current_time = time.time()
            # Use a longer cleanup window for rate limit entries to avoid deleting active short-term blocks
            rate_limit_cleanup_window = max(CONFIG.get('RATE_LIMIT_WINDOW', 60), CONFIG.get('DETECT_RATE_LIMIT_WINDOW', 60), 3600) # e.g., 1 hour
            
            keys_to_delete = []
            for client_ip, timestamps in list(rate_limit_storage.items()): # Iterate over a copy for safe deletion
                # Filter out old timestamps
                valid_timestamps = [ts for ts in timestamps if ts > current_time - rate_limit_cleanup_window]
                if not valid_timestamps:
                    keys_to_delete.append(client_ip)
                else:
                    rate_limit_storage[client_ip] = valid_timestamps
            
            for key in keys_to_delete:
                if key in rate_limit_storage: # Check again before deleting
                    del rate_limit_storage[key]
                    logger.debug(f"Cleaned up stale rate limit entry for IP: {key}")

            cleanup_old_logs() # Also run scheduled old log file cleanup

            time.sleep(300)  # Check every 5 minutes
            
        except Exception as e:
            logger.error(f"Error in log monitor thread: {e}", exc_info=True)
            time.sleep(60)  # Wait 1 minute before retrying on error

if __name__ == '__main__':
    if not os.path.exists(CONFIG['LOG_FILE']):
        log_line, _ = create_log_entry('INFO', 'Detection log system started', 'SYSTEM')
        write_log(log_line, broadcast=False) # Don't broadcast initial startup if no clients yet
    
    monitor_thread = threading.Thread(target=log_monitor, daemon=True)
    monitor_thread.start()
    
    logger.info("Starting Flask application with SocketIO...")
    print(f"Dashboard will be available at: http://localhost:5000 (or http://<your_ip>:5000)")
    print(f"Default credentials - Username: {CONFIG['USERNAME']}, Password: {CONFIG['PASSWORD']}")
    print(f"Rate limit for /detect: {CONFIG['DETECT_RATE_LIMIT_MAX']} requests / {CONFIG['DETECT_RATE_LIMIT_WINDOW']} seconds")
    print("\n🔧 Troubleshooting:")
    print(f"If you get rate limit errors, wait up to {CONFIG['DETECT_RATE_LIMIT_WINDOW']} seconds or adjust DETECT_RATE_LIMIT_MAX in server.py CONFIG.")
    
    # Optionally clear log file on startup for debug, but usually not desired for persistence.
    # if os.path.exists(CONFIG['LOG_FILE']) and app.debug: # Only in debug mode
    #     with open(CONFIG['LOG_FILE'], 'w') as f:
    #         f.write("") # Clear log file
    #     logger.info("Log file cleared on startup (DEBUG MODE).")
            
    socketio.run(
        app, 
        debug=True, # Set to False in production
        host='0.0.0.0', 
        port=5000,
        allow_unsafe_werkzeug=True # Only for Werkzeug dev server, use a proper WSGI server in prod
    )