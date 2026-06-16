import cv2
import numpy as np
import requests
from keras.models import load_model
from collections import deque
from datetime import timedelta, datetime
import csv
import os
import time
import threading
from queue import Queue, Empty
import json
import argparse
import sys
from urllib.parse import urlparse
import socket
import uuid
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_email_alert(subject, message):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("📧 Email alert sent!")
    except Exception as e:
        print(f"❌ Email alert failed: {e}")

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("🤖 Telegram alert sent!")
        else:
            print(f"❌ Telegram alert failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

class InputMode:
    VIDEO_FILE = "video"
    ESP32_CAM = "esp32cam"
    WEBCAM = "webcam"

DEFAULT_CONFIG = {
    'INPUT_MODE': InputMode.VIDEO_FILE,
    'VIDEO_FILE': "violence.mp4",
    'ESP32_CAM_IP': "192.168.1.100",
}

ESP32_CAM_CONFIG = {
    'STREAM_URLS': [
        'http://{ip}/stream',
    ],
    'CONNECTION_TIMEOUT': 10,
    'READ_TIMEOUT': 5,
    'RECONNECT_DELAY': 2,
    'MAX_RECONNECT_ATTEMPTS': 5,
    'SKIP_FRAMES': 2,
    'BUFFER_SIZE': 1024 * 8,
    'MODE': 'requests',
}

MODEL_PATH = "BILSTM_RESNET_MODEL.h5"
SEQUENCE_LENGTH = 16
IMG_SIZE = 64
API_URL = "http://127.0.0.1:5000/detect"
LOG_PATH = "logs/violence_events.csv"

VIOLENCE_EVENT_WINDOW = 10.0
MIN_CONFIDENCE_FOR_EVENT = 0.6
HIGH_CONFIDENCE_THRESHOLD = 0.8
MIN_DETECTIONS_FOR_EVENT = 3
API_RETRY_ATTEMPTS = 2
API_TIMEOUT = 10

# === Improved ESP32-CAM Stream Handler ===
class ESP32CamStream:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.stream_url = None
        self.cap = None
        self.connected = False
        self.last_frame = None
        self.frame_count = 0
        self.reconnect_count = 0
        self.session = requests.Session()
        self.streaming_response = None
        self.bytes_buffer = b""
        self.mjpeg_iterator = None
        
    def test_connection(self, url):
        try:
            parsed_url = urlparse(url)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((parsed_url.hostname, parsed_url.port or 80))
            sock.close()
            
            if result != 0:
                return False, "Port not reachable"
            
            response = self.session.get(url, timeout=5, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                if 'multipart' in content_type or 'video' in content_type or 'image' in content_type:
                    response.close()
                    return True, "Valid stream"
                else:
                    response.close()
                    return False, f"Not a video stream (content-type: {content_type})"
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    def find_working_url(self):
        print(f"🔍 Scanning for ESP32-CAM at IP: {self.ip_address}")
        for i, url_pattern in enumerate(ESP32_CAM_CONFIG['STREAM_URLS'], 1):
            url = url_pattern.format(ip=self.ip_address)
            print(f"[{i}/{len(ESP32_CAM_CONFIG['STREAM_URLS'])}] Testing: {url}")
            success, message = self.test_connection(url)
            if success:
                print(f"✅ ESP32-CAM found at: {url}")
                return url
            else:
                print(f"❌ Failed: {message}")
        return None
    
    def connect(self):
        print(f"🔌 Connecting to ESP32-CAM at IP: {self.ip_address}")
        self.stream_url = self.find_working_url()
        if not self.stream_url:
            print("❌ No working ESP32-CAM URL found!")
            print("💡 Troubleshooting tips:")
            print("   1. Check if ESP32-CAM is powered on")
            print(f"   2. Verify IP address with: ping {self.ip_address}")
            print("   3. Try opening the stream URL in a browser")
            print("   4. Check if the ESP32-CAM firmware supports /stream endpoint")
            return False
        
        methods = [self._connect_requests_stream]
        for i, method in enumerate(methods, 1):
            print(f"🔄 Trying connection method {i}/{len(methods)}...")
            if method():
                self.connected = True
                print(f"✅ ESP32-CAM connected using method {i}!")
                return True
        print("❌ All connection methods failed")
        return False
    
    def _connect_requests_stream(self):
        try:
            response = self.session.get(self.stream_url, stream=True, timeout=(ESP32_CAM_CONFIG['CONNECTION_TIMEOUT'], ESP32_CAM_CONFIG['READ_TIMEOUT']))
            if response.status_code == 200:
                self.streaming_response = response
                self.bytes_buffer = b""
                self.mjpeg_iterator = self._mjpeg_generator(response)
                print("   Using requests-based MJPEG streaming")
                return True
            return False
        except Exception as e:
            print(f"   Error connecting with requests stream: {e}")
            return False
    
    def _mjpeg_generator(self, response):
        for chunk in response.iter_content(chunk_size=ESP32_CAM_CONFIG['BUFFER_SIZE']):
            self.bytes_buffer += chunk
            start = self.bytes_buffer.find(b'\xff\xd8')
            end = self.bytes_buffer.find(b'\xff\xd9')
            if start != -1 and end != -1 and end > start:
                jpg = self.bytes_buffer[start:end+2]
                self.bytes_buffer = self.bytes_buffer[end+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    yield frame
    
    def read_frame(self):
        if self.streaming_response and self.mjpeg_iterator:
            try:
                frame = next(self.mjpeg_iterator)
                if frame is not None and frame.size > 0:
                    self.last_frame = frame
                    return frame
                else:
                    return self.last_frame 
            except StopIteration:
                print("⚠️ MJPEG stream ended")
                self.disconnect() # Attempt to clean up
                if self.attempt_reconnect(): # Try to reconnect
                     return self.last_frame # Return last frame while reconnecting
                return None # Stream truly ended or failed reconnect
            except Exception as e:
                print(f"⚠️ MJPEG parse error: {e}")
                # Potentially try to re-establish iterator or reconnect
                self.disconnect()
                if self.attempt_reconnect():
                    return self.last_frame
                return self.last_frame # Return last good frame on minor parse error
        
        # If not connected or error, try to reconnect
        if not self.connected:
            if self.attempt_reconnect():
                return self.last_frame # Return last frame if reconnect was successful
            else: # Failed to reconnect after attempts
                return None 
        
        return self.last_frame # Fallback, return last known frame

    def attempt_reconnect(self):
        if self.reconnect_count >= ESP32_CAM_CONFIG['MAX_RECONNECT_ATTEMPTS']:
            print(f"❌ Max reconnection attempts reached for {self.ip_address}")
            return False
        
        self.reconnect_count += 1
        print(f"🔄 Reconnecting to {self.ip_address}... (attempt {self.reconnect_count})")
        self.disconnect() # Ensure clean state before reconnect
        time.sleep(ESP32_CAM_CONFIG['RECONNECT_DELAY'])
        if self.connect(): # Try to connect again
            self.reconnect_count = 0 # Reset on successful reconnect
            return True
        return False
    
    def disconnect(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.streaming_response:
            try:
                self.streaming_response.close()
            except Exception:
                pass # Ignore errors on close
            self.streaming_response = None
        self.connected = False
        self.mjpeg_iterator = None
        self.bytes_buffer = b""
        # print("🔌 ESP32-CAM disconnected") # Less verbose during auto-reconnect

# === Video Input Manager ===
class VideoInputManager:
    def __init__(self, mode, **kwargs):
        self.mode = mode
        self.cap = None
        self.esp32_stream = None
        self.frame_skip_counter = 0
        
        if mode == InputMode.VIDEO_FILE:
            self.video_file = kwargs.get('video_file', DEFAULT_CONFIG['VIDEO_FILE'])
        elif mode == InputMode.ESP32_CAM:
            self.esp32_ip = kwargs.get('esp32_ip', DEFAULT_CONFIG['ESP32_CAM_IP'])
        
    def initialize(self):
        print(f"🎥 Initializing {self.mode.upper()} input...")
        if self.mode == InputMode.VIDEO_FILE:
            return self._init_video_file()
        elif self.mode == InputMode.ESP32_CAM:
            return self._init_esp32_cam()
        elif self.mode == InputMode.WEBCAM:
            return self._init_webcam()
        else:
            print(f"❌ Unknown input mode: {self.mode}")
            return False
    
    def _init_video_file(self):
        if not os.path.exists(self.video_file):
            print(f"❌ Video file not found: {self.video_file}")
            return False
        self.cap = cv2.VideoCapture(self.video_file)
        if not self.cap.isOpened():
            print(f"❌ Could not open video file: {self.video_file}")
            return False
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        print(f"✅ Video loaded: {self.video_file} ({frame_count} frames, {fps:.1f} FPS, {duration:.1f}s duration)")
        return True
    
    def _init_esp32_cam(self):
        self.esp32_stream = ESP32CamStream(self.esp32_ip)
        return self.esp32_stream.connect()
    
    def _init_webcam(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("❌ Could not open webcam")
            return False
        print("✅ Webcam initialized")
        return True
    
    def read_frame(self):
        if self.mode == InputMode.ESP32_CAM:
            if self.esp32_stream:
                frame = self.esp32_stream.read_frame()
                if frame is None and not self.esp32_stream.connected: # If read_frame returns None and not connected, means connection failed
                    print("Lost connection to ESP32-CAM, read_frame returned None.")
                    # Attempt_reconnect is handled within esp32_stream.read_frame()
                    return None, False # Indicate failure to get frame
                
                # Frame skipping logic
                if frame is not None:
                    self.frame_skip_counter += 1
                    if self.frame_skip_counter <= ESP32_CAM_CONFIG['SKIP_FRAMES']:
                        return frame, True  # Skip processing
                    else:
                        self.frame_skip_counter = 0
                        return frame, False  # Process this frame
                return frame, False # Potentially None if error in stream
            return None, False
        else: # Video file or webcam
            if self.cap:
                ret, frame = self.cap.read()
                return frame if ret else None, False
            return None, False
    
    def get_timestamp(self):
        if self.mode == InputMode.VIDEO_FILE and self.cap and self.cap.isOpened():
            return self.cap.get(cv2.CAP_PROP_POS_MSEC)
        else:
            return time.time() * 1000
    
    def cleanup(self):
        if self.cap:
            self.cap.release()
        if self.esp32_stream:
            self.esp32_stream.disconnect()

# === Violence Event Class ===
class ViolenceEvent:
    def __init__(self):
        self.event_id = str(uuid.uuid4())
        self.start_time = None
        self.end_time = None # Set at the actual end of the event
        self.detections = []
        self.max_confidence = 0.0
        self.avg_confidence = 0.0
        self.frame_count = 0
        self.last_report_time_api = None # Timestamp of the last API report (start or update)
        self.last_detection_timestamp = None # Timestamp of the last actual violence frame

    def add_detection(self, timestamp, confidence, frame_num):
        # start_time is set when the event object is first created
        self.last_detection_timestamp = timestamp # Update time of last actual violence
        
        confidence_float = float(confidence)
        self.detections.append({
            'timestamp': timestamp.isoformat(), # Store ISO format string
            'confidence': confidence_float,
            'frame': int(frame_num)
        })
        
        self.max_confidence = max(self.max_confidence, confidence_float)
        self.frame_count += 1
        if self.detections:
             self.avg_confidence = sum(d['confidence'] for d in self.detections) / len(self.detections)
        else:
             self.avg_confidence = 0.0
    
    def get_current_duration(self, current_event_time=None):
        if self.start_time:
            effective_end_time = current_event_time if current_event_time else (self.last_detection_timestamp or self.start_time)
            return (effective_end_time - self.start_time).total_seconds()
        return 0
    
    def get_final_duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return self.get_current_duration(self.last_detection_timestamp) # Fallback if end_time not explicitly set

    def should_report_finally(self): # Condition for the event to be significant
        return (
            self.frame_count >= MIN_DETECTIONS_FOR_EVENT and
            self.max_confidence >= MIN_CONFIDENCE_FOR_EVENT
        )
    
    def get_severity(self):
        if self.max_confidence >= HIGH_CONFIDENCE_THRESHOLD:
            return "HIGH"
        elif self.max_confidence >= 0.7:
            return "MEDIUM"
        else:
            return "LOW"

# === Global variables ===
frame_buffer = deque(maxlen=SEQUENCE_LENGTH)
current_violence_event = None
last_detected_violence_activity_time = None # Timestamp of the last frame classified as violent
event_log = []
api_queue = Queue()
args = None # Will hold command line arguments

# === Utility functions ===
def make_json_serializable(obj):
    if isinstance(obj, np.integer): return int(obj)
    elif isinstance(obj, np.floating): return float(obj)
    elif isinstance(obj, np.ndarray): return obj.tolist()
    elif isinstance(obj, datetime): return obj.isoformat()
    elif isinstance(obj, timedelta): return obj.total_seconds()
    elif isinstance(obj, dict): return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list): return [make_json_serializable(item) for item in obj]
    else: return obj

def preprocess_frame(frame):
    frame = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
    frame = frame.astype("float32") / 255.0
    return frame

def format_timestamp(ms):
    if ms is None: return "N/A"
    try:
        return str(timedelta(milliseconds=ms)).split(".")[0]
    except:
        return "N/A"

# === API Communication ===
def create_event_snapshot(event_obj, report_datetime, input_mode_str, is_final=False):
    if not event_obj: return {}

    if is_final:
        duration = event_obj.get_final_duration()
        # Ensure end_time is set, otherwise use last_detection_timestamp or report_datetime
        final_end_time = event_obj.end_time or event_obj.last_detection_timestamp or report_datetime
        end_time_iso = final_end_time.isoformat()
    else:
        duration = event_obj.get_current_duration(current_event_time=report_datetime)
        # For ongoing reports, 'end_time' conceptually is the 'report_datetime'
        end_time_iso = report_datetime.isoformat() 

    data = {
        "start_time": event_obj.start_time.isoformat() if event_obj.start_time else report_datetime.isoformat(),
        "current_report_time": report_datetime.isoformat(),
        "duration_seconds": float(round(duration, 1)),
        "max_confidence": float(round(event_obj.max_confidence, 2)),
        "avg_confidence": float(round(event_obj.avg_confidence, 2)),
        "detection_count": int(event_obj.frame_count),
        "severity": event_obj.get_severity(),
        "source": f"{input_mode_str}_violence_detection",
    }
    if is_final:
        data["end_time"] = end_time_iso # Official end of event for final report
    
    return make_json_serializable(data)

def send_event_to_api(event_snapshot, report_type, event_id, input_mode):
    message_action = report_type.split('_')[-1].lower()
    duration_info = f"duration {event_snapshot.get('duration_seconds', 0):.1f}s" if 'duration_seconds' in event_snapshot else ""
    
    event_data = {
        "event_id": event_id,
        "type": report_type,
        "severity": event_snapshot.get('severity', 'UNKNOWN'),
        "message": f"Violence event {message_action} via {input_mode}. {duration_info}",
        "details": event_snapshot, # Already JSON serializable
    }
    
    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            print(f"📡 Sending {report_type} (ID: {event_id[:8]}...) to API (attempt {attempt + 1})...")
            response = requests.post(API_URL, json=event_data, timeout=API_TIMEOUT)
            
            if response.status_code == 200:
                print(f"✅ {report_type} (ID: {event_id[:8]}) sent successfully")
                return True
            else:
                print(f"⚠️ API for {report_type} (ID: {event_id[:8]}) returned {response.status_code}: {response.text}")
                if attempt < API_RETRY_ATTEMPTS - 1:
                    print(f"⏳ Waiting 2s before retry...")
                    time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"⚠️ API error for {report_type} (ID: {event_id[:8]}): {str(e)[:100]}...")
            if attempt < API_RETRY_ATTEMPTS - 1: time.sleep(1)
    
    print(f"❌ Failed to send {report_type} (ID: {event_id[:8]}) to API after {API_RETRY_ATTEMPTS} attempts.")
    return False

# === Violence Detection Logic ===
def process_violence_detection(prediction, frame_num, input_mode_str):
    global current_violence_event, last_detected_violence_activity_time
    
    processing_timestamp = datetime.now()
    is_violence = prediction >= MIN_CONFIDENCE_FOR_EVENT
    status_message = "Monitoring"

    if is_violence:
        if current_violence_event is None:
            current_violence_event = ViolenceEvent()
            current_violence_event.start_time = processing_timestamp
            # Add detection first so max_confidence is updated for get_severity()
            current_violence_event.add_detection(processing_timestamp, prediction, frame_num)
            current_violence_event.last_report_time_api = processing_timestamp # For 2s interval calc
            
            event_id_short = current_violence_event.event_id[:8]
            timestamp_str = processing_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            current_severity = current_violence_event.get_severity() # Get severity after detection added
            
            print(f"\n🚨 NEW VIOLENCE EVENT (ID: {event_id_short}...) at {timestamp_str}")
            
            # Prepare alert messages
            alert_subject = f"Violence Detected: Event {event_id_short}"
            alert_message_body = (
                f"A new violence event (ID: {event_id_short}) was detected.\n"
                f"Time: {timestamp_str}\n"
                f"Source: {input_mode_str.upper()}\n"
                f"Initial Confidence: {prediction:.2f}\n"
                f"Severity: {current_severity}"
            )
            
            # Send Email Alert
            if EMAIL_USER and EMAIL_PASS and EMAIL_TO:
                # Run in a new thread to avoid blocking
                threading.Thread(target=send_email_alert, args=(alert_subject, alert_message_body)).start()
            else:
                print("⚠️ Email credentials not configured. Skipping email alert.")

            # Send Telegram Alert
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                if current_severity == "HIGH":
                    telegram_message = (
                        f"🚨 *⚠️ CRITICAL VIOLENCE DETECTED!* 🚨\n\n"
                        f"🆔 *Event ID:* `{event_id_short}`\n"
                        f"🕒 *Time:* `{timestamp_str}`\n"
                        f"🎥 *Source:* `{input_mode_str.upper()}`\n"
                        f"📈 *Confidence:* *{prediction:.2f}*\n"
                        f"🔥 *Severity:* *HIGH*\n\n"
                        f"🚔 Immediate attention required!"
                    )
                elif current_severity == "MEDIUM":
                    telegram_message = (
                        f"🚨 *Violence Event Alert* 🚨\n\n"
                        f"🆔 *Event ID:* `{event_id_short}`\n"
                        f"🕒 *Time:* `{timestamp_str}`\n"
                        f"🎥 *Source:* `{input_mode_str.upper()}`\n"
                        f"📈 *Confidence:* *{prediction:.2f}*\n"
                        f"⚠️ *Severity:* *MEDIUM*\n\n"
                        f"⚠️ Please monitor the situation closely."
                    )
                else:
                    telegram_message = (
                        f"📡 *Possible Violence Detected* 📡\n\n"
                        f"🆔 *Event ID:* `{event_id_short}`\n"
                        f"🕒 *Time:* `{timestamp_str}`\n"
                        f"🎥 *Source:* `{input_mode_str.upper()}`\n"
                        f"📈 *Confidence:* *{prediction:.2f}*\n"
                        f"🟡 *Severity:* *LOW*\n\n"
                        f"👀 Monitoring in progress."
                    )
                # Run in a new thread to avoid blocking
                threading.Thread(target=send_telegram_alert, args=(telegram_message,)).start()
            else:
                print("⚠️ Telegram credentials not configured. Skipping Telegram alert.")

            snapshot_data = create_event_snapshot(current_violence_event, processing_timestamp, input_mode_str, is_final=False)
            api_queue.put(("VIOLENCE_START", current_violence_event.event_id, snapshot_data, input_mode_str))
        else:
            current_violence_event.add_detection(processing_timestamp, prediction, frame_num)
            # Update event severity if it changes due to new higher confidence
            current_severity = current_violence_event.get_severity() 
            if (processing_timestamp - current_violence_event.last_report_time_api).total_seconds() >= 2.0:
                print(f"🔄 VIOLENCE UPDATE (ID: {current_violence_event.event_id[:8]}...) at {processing_timestamp.strftime('%H:%M:%S')}")
                snapshot_data = create_event_snapshot(current_violence_event, processing_timestamp, input_mode_str, is_final=False)
                api_queue.put(("VIOLENCE_UPDATE", current_violence_event.event_id, snapshot_data, input_mode_str))
                current_violence_event.last_report_time_api = processing_timestamp
        
        last_detected_violence_activity_time = processing_timestamp
        status_message = f"Event Active (ID: {current_violence_event.event_id[:8]}) Sev: {current_severity}"
    else: # Not violence
        if current_violence_event is not None:
            if last_detected_violence_activity_time and \
               (processing_timestamp - last_detected_violence_activity_time).total_seconds() >= VIOLENCE_EVENT_WINDOW:
                finalize_current_event(input_mode_str, processing_timestamp)
        status_message = "Monitoring"
            
    return status_message

def finalize_current_event(input_mode_str, event_conclusion_time):
    global current_violence_event
    
    if current_violence_event and current_violence_event.should_report_finally():
        current_violence_event.end_time = current_violence_event.last_detection_timestamp or event_conclusion_time
        
        print(f"🔚 Violence event (ID: {current_violence_event.event_id[:8]}) ended:")
        print(f"   Duration: {current_violence_event.get_final_duration():.1f}s")
        print(f"   Detections: {current_violence_event.frame_count}")
        print(f"   Max confidence: {current_violence_event.max_confidence:.2f}")
        
        snapshot_data = create_event_snapshot(current_violence_event, event_conclusion_time, input_mode_str, is_final=True)
        api_queue.put(("VIOLENCE_END", current_violence_event.event_id, snapshot_data, input_mode_str))
        
        event_log.append({
            'event_id': current_violence_event.event_id,
            'start_time': current_violence_event.start_time.isoformat(),
            'end_time': current_violence_event.end_time.isoformat(),
            'duration': float(round(current_violence_event.get_final_duration(), 1)),
            'detections': int(current_violence_event.frame_count),
            'max_confidence': float(round(current_violence_event.max_confidence, 2)),
            'avg_confidence': float(round(current_violence_event.avg_confidence, 2)),
            'severity': current_violence_event.get_severity()
        })
    elif current_violence_event:
         print(f"เท Event (ID: {current_violence_event.event_id[:8]}) insignificant. Discarding final report.")
    
    current_violence_event = None

def api_worker():
    while True:
        try:
            report_type, event_id, snapshot_data, input_mode_str = api_queue.get(timeout=1)
            if report_type is None: # Sentinel
                api_queue.task_done()
                break
            send_event_to_api(snapshot_data, report_type, event_id, input_mode_str)
            api_queue.task_done()
            time.sleep(2)
        except Empty:
            continue
        except Exception as e:
            print(f"Error in API worker: {e}")
            # Consider if task_done should be called here or if item should be re-queued
            # For simplicity, assuming item is consumed on error for now.
            if api_queue.unfinished_tasks > 0 : # Check if get was successful before task_done
                 api_queue.task_done()


# === Main Function ===
def main():
    global args, current_violence_event, last_detected_violence_activity_time, frame_buffer, event_log # Declare globals used in main

    parser = argparse.ArgumentParser(description='Violence Detection System')
    parser.add_argument('--mode', choices=['video', 'esp32cam', 'webcam'], default=DEFAULT_CONFIG['INPUT_MODE'], help='Input source mode')
    parser.add_argument('--video', default=DEFAULT_CONFIG['VIDEO_FILE'], help='Video file path')
    parser.add_argument('--ip', default=DEFAULT_CONFIG['ESP32_CAM_IP'], help='ESP32-CAM IP address')
    args = parser.parse_args() # Assign to global args
    
    print("🎯 VIOLENCE DETECTION SYSTEM\n" + "=" * 40)
    print(f"🎮 Mode: {args.mode.upper()}")
    if args.mode == 'video': print(f"📁 Video file: {args.video}")
    elif args.mode == 'esp32cam': print(f"📡 ESP32-CAM IP: {args.ip}")
    print(f"🤖 Model: {MODEL_PATH}\n📡 API endpoint: {API_URL}\n" + "=" * 40)
    
    print("🔍 Loading violence detection model...")
    try:
        model = load_model(MODEL_PATH)
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading model: {e}"); return
    
    input_manager = VideoInputManager(args.mode, video_file=args.video, esp32_ip=args.ip)
    if not input_manager.initialize():
        print("❌ Failed to initialize input source"); return
    
    api_thread = threading.Thread(target=api_worker, daemon=True)
    api_thread.start()
    
    frame_count = 0
    processed_frames = 0
    violence_frames = 0
    
    print(f"🚀 Starting {args.mode} violence detection...\nPress 'q' to quit, 's' to save current stats")
    
    try:
        while True:
            frame, should_skip = input_manager.read_frame()
            if frame is None:
                if args.mode == 'video': print("📹 End of video"); break
                else: # Webcam or ESP32 might return None temporarily
                    if input_manager.mode == InputMode.ESP32_CAM and not input_manager.esp32_stream.connected:
                        print("ESP32-CAM appears disconnected. Ending loop.")
                        break # Exit if ESP32-CAM is definitively disconnected
                    time.sleep(0.1) # Brief pause for live feeds
                    continue 
            
            frame_count += 1
            if should_skip: continue
            
            processed_frames += 1
            # current_time_ms for display, actual event timing uses datetime.now()
            display_time_ms = input_manager.get_timestamp() 
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            processed = preprocess_frame(rgb_frame)
            frame_buffer.append(processed)
            
            status = "Buffering..."
            if len(frame_buffer) == SEQUENCE_LENGTH:
                input_batch = np.expand_dims(np.array(frame_buffer), axis=0)
                prediction = model.predict(input_batch, verbose=0)[0][0]
                
                status = process_violence_detection(prediction, processed_frames, args.mode)
                
                if prediction >= MIN_CONFIDENCE_FOR_EVENT: violence_frames += 1
                
                label = f"VIOLENCE ({prediction:.2f})" if prediction >= MIN_CONFIDENCE_FOR_EVENT else f"Safe ({prediction:.2f})"
                color = (0, 0, 255) if prediction >= MIN_CONFIDENCE_FOR_EVENT else (0, 255, 0)
                cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            cv2.putText(frame, f"Status: {status}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Source: {args.mode.upper()}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            stats_text = f"Processed: {processed_frames} | Violence: {violence_frames} | Events: {len(event_log)}"
            cv2.putText(frame, stats_text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if current_violence_event:
                event_info = f"Event: {current_violence_event.frame_count} dets, {current_violence_event.get_current_duration(datetime.now()):.1f}s"
                cv2.putText(frame, event_info, (10, frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            cv2.imshow(f"Violence Detection - {args.mode.upper()} (Press 'q' to quit)", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): print("🛑 User requested quit"); break
            elif key == ord('s'):
                print(f"\n📊 Current Stats:\n   Total frames: {frame_count}\n   Processed: {processed_frames}\n   Violence: {violence_frames}\n   Events: {len(event_log)}")
    
    except KeyboardInterrupt: print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if current_violence_event: # Ensure any active event is finalized
            finalize_current_event(args.mode, datetime.now())
        
        print("⏳ Finishing up...")
        api_queue.put((None, None, None, None)) # Sentinel to stop API worker
        api_queue.join() # Wait for all API tasks to complete
        
        input_manager.cleanup()
        cv2.destroyAllWindows()
        
        os.makedirs("logs", exist_ok=True)
        if event_log:
            # Updated fieldnames to include event_id and use ISO format for timestamps
            fieldnames = ['event_id', "start_time", "end_time", "duration", "detections", 
                          "max_confidence", "avg_confidence", "severity"]
            with open(LOG_PATH, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(event_log)
        
        print("\n" + "="*50 + "\n📊 DETECTION SUMMARY\n" + "="*50)
        print(f"🎮 Input mode: {args.mode.upper()}\n📽️  Total frames: {frame_count}\n🔍 Processed frames: {processed_frames}")
        print(f"🚨 Violence frames: {violence_frames}\n📋 Violence events: {len(event_log)}")
        if event_log:
            print(f"\n🔍 Event Details:")
            for i, event in enumerate(event_log, 1):
                print(f"  {i}. ID: {event['event_id'][:8]}... {event['start_time']} to {event['end_time']} "
                      f"({event['duration']}s, {event['detections']} detections, conf: {event['max_confidence']:.2f}, sev: {event['severity']})")
        print(f"\n✅ Logs saved to: {LOG_PATH}\n✅ Detection completed!")

if __name__ == "__main__":
    print("🎯 Violence Detection System")
    print("💡 Usage examples:")
    print("   python violence_detection.py --mode video --video violence.mp4")
    print("   python violence_detection.py --mode esp32cam --ip 192.168.1.100")
    print("   python violence_detection.py --mode webcam")
    print("   (or just run `python violence_detection.py` for defaults)\n")
    main()