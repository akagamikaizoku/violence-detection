# 🎯 Real-Time Violence Detection System

A comprehensive, real-time violence detection system that combines state-of-the-art deep learning models with a modern, feature-rich web interface. It actively monitors video streams (files, webcams, or IP cameras like ESP32-CAM) to identify violent activities and dispatches immediate alerts via Email and Telegram.

---

## ✨ Key Features

### 🧠 Core AI Detection
- **Multiple Supported Models**: Highly accurate pre-trained deep learning models including:
  - BILSTM with ResNet backbone
  - BILSTM with VGG16 backbone
  - LSTM with MobileNet backbone
  - MoBiLSTM model
- **Real-time Processing**: Frame sequence-based analysis for precise temporal detection.
- **Versatile Input Sources**: 
  - Local Video Files (`.mp4`, etc.)
  - USB Webcams
  - IP Cameras (ESP32-CAM integrated)

### 🚨 Intelligent Alerting System
- **Email Notifications**: Automated, detailed email alerts with timestamp, confidence score, and event details.
- **Telegram Bot Integration**: Instant alerts delivered to your Telegram app based on severity levels (High/Medium/Low).
- **Comprehensive Logging**: All events are logged locally in a `.csv` format (`logs/violence_events.csv`).
- **Configurable Thresholds**: Easily adjustable confidence minimums to reduce false positives.

### 🎨 Modern Web Dashboard
- **Real-Time Monitoring**: Live detection feed and event statistics via WebSockets (`flask-socketio`).
- **Secure Authentication**: Built-in login system with session management and rate limiting.
- **Enhanced UI/UX**:
  - 🌓 **Dark Mode / Light Mode** with persistent local storage.
  - 🧊 **Glassmorphism Design** featuring backdrop blur and smooth animations.
  - 🔔 **Toast Notification System** for user actions.
  - 📊 **Responsive Layout** optimized for all device sizes.
  - 🎭 **FontAwesome Integration** for intuitive iconography.

---

## 📋 Prerequisites

- **Python 3.7+**
- Pre-trained `.h5` model files (e.g., `BILSTM_RESNET_MODEL.h5`) placed in the root directory.
- (Optional but recommended) **CUDA/cuDNN** for GPU acceleration.

### Python Dependencies
```text
opencv-python
numpy
keras
tensorflow
flask
flask-socketio
python-dotenv
requests
```

---

## 🚀 Setup & Installation

### 1. Clone & Install
```bash
git clone <your-repository-url>
cd projectW
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the project root to securely store your credentials:
```env
# Email Configuration
EMAIL_USER="your_email@gmail.com"
EMAIL_PASS="your_app_password"
EMAIL_TO="recipient@example.com"

# Telegram Configuration
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"
```

### 3. Model Setup
Ensure at least one of the `.h5` models is in the root directory. The system defaults to `BILSTM_RESNET_MODEL.h5`.

---

## 🎮 Usage Guide

### Starting the Detection Engine
Run the detection script with your preferred input source:

```bash
# Detect from local video file (default: violence.mp4)
python violence_detection.py --mode video --video violence.mp4

# Detect from local webcam
python violence_detection.py --mode webcam

# Detect from ESP32-CAM
python violence_detection.py --mode esp32cam --ip 192.168.1.100
```

### Starting the Web Dashboard
In a separate terminal, launch the Flask server:
```bash
python server.py
```
Open your browser and navigate to `http://localhost:5000`.
- **Default Login**: `admin` / `password123` *(Remember to change this in production!)*

### Diagnostics & Troubleshooting
Experiencing connection issues with your ESP32-CAM? We have built a diagnostic tool to help:
```bash
python test.py
```
This script tests basic network connectivity, open ports, HTTP endpoints, and OpenCV stream compatibility.

---

## 📁 Project Structure

```text
projectW/
├── violence_detection.py      # Main CV & AI detection engine
├── server.py                  # Flask web dashboard server
├── test.py                    # ESP32-CAM diagnostics script
├── .env                       # Environment credentials (Git-ignored)
├── *.h5                       # Pre-trained deep learning models
├── logs/
│   └── violence_events.csv    # Recorded detection events
├── static/                    # Frontend assets (CSS, JS, animations)
├── templates/                 # HTML UI templates (Dashboard, Login)
└── WEB_ENHANCEMENTS.md        # Detailed breakdown of UI/UX features
```

---

## ⚙️ Configuration Details

**Detection Tweaks (`violence_detection.py`)**
- `SEQUENCE_LENGTH`: Number of frames for sequential analysis (Default: 16).
- `MIN_CONFIDENCE_FOR_EVENT`: Threshold to trigger violence alerts (Default: 0.6).
- `VIOLENCE_EVENT_WINDOW`: Reset window for contiguous events (Default: 10s).

**Server Tuning (`server.py`)**
- `SESSION_TIMEOUT`: Dashboard expiration limit.
- `RATE_LIMIT_MAX`: API rate limits to prevent brute-force or spam attacks.

---

## 🔒 Security Best Practices
- **Never commit your `.env` file** to version control.
- Change the default `admin` password inside `server.py` before deploying to production.
- Consider deploying the Flask application using a production WSGI server (like Gunicorn) and securing the endpoints with HTTPS.

---

*Built with ❤️ for safer environments.*
