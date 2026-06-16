#!/usr/bin/env python3
"""
ESP32-CAM Connection Debug and Test Script
This script helps diagnose and fix ESP32-CAM connection issues
"""

import requests
import cv2
import time
import socket
from urllib.parse import urlparse

def test_ping(ip):
    """Test basic network connectivity"""
    print(f"🔍 Testing network connectivity to {ip}...")
    import subprocess
    import platform
    
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', ip]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Ping successful to {ip}")
            return True
        else:
            print(f"❌ Ping failed to {ip}")
            return False
    except Exception as e:
        print(f"❌ Ping error: {e}")
        return False

def test_port_connectivity(ip, port):
    """Test if a specific port is open"""
    print(f"🔍 Testing port {port} on {ip}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    
    try:
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            print(f"✅ Port {port} is open")
            return True
        else:
            print(f"❌ Port {port} is closed or filtered")
            return False
    except Exception as e:
        print(f"❌ Port test error: {e}")
        return False

def test_http_endpoint(url, timeout=10):
    """Test HTTP endpoint with detailed error info"""
    print(f"🔍 Testing HTTP endpoint: {url}")
    
    try:
        # First test with a simple GET request
        response = requests.get(url, timeout=timeout, stream=False)
        print(f"✅ HTTP GET successful - Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        print(f"   Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
        return True, response
        
    except requests.exceptions.ConnectTimeout:
        print(f"❌ Connection timeout - ESP32-CAM may be busy or overloaded")
        return False, None
    except requests.exceptions.ReadTimeout:
        print(f"❌ Read timeout - ESP32-CAM is not responding fast enough")
        return False, None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {str(e)}")
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False, None

def test_cv2_stream(url, timeout=30):
    """Test OpenCV video capture from URL"""
    print(f"🔍 Testing OpenCV VideoCapture with: {url}")
    
    try:
        cap = cv2.VideoCapture(url)
        
        # Set timeout properties
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Try to read a frame with timeout
        start_time = time.time()
        success = False
        
        while (time.time() - start_time) < timeout:
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"✅ OpenCV successfully captured frame")
                print(f"   Frame shape: {frame.shape}")
                success = True
                break
            time.sleep(0.1)
        
        cap.release()
        
        if not success:
            print(f"❌ OpenCV failed to capture frame within {timeout} seconds")
        
        return success
        
    except Exception as e:
        print(f"❌ OpenCV error: {str(e)}")
        return False

def main():
    print("🎯 ESP32-CAM CONNECTION DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Get IP from user or use default
    ip = input("Enter ESP32-CAM IP address (default: 192.168.222.62): ").strip()
    if not ip:
        ip = "192.168.222.62"
    
    print(f"\n🔍 Diagnosing connection to ESP32-CAM at {ip}")
    print("-" * 40)
    
    # Step 1: Test basic network connectivity
    if not test_ping(ip):
        print("\n❌ Basic network connectivity failed!")
        print("💡 Check:")
        print("   - ESP32-CAM is powered on")
        print("   - Both devices are on the same network")
        print("   - IP address is correct")
        return
    
    # Step 2: Test common ports
    ports_to_test = [80, 81, 8080]
    open_ports = []
    
    for port in ports_to_test:
        if test_port_connectivity(ip, port):
            open_ports.append(port)
    
    if not open_ports:
        print("\n❌ No HTTP ports are accessible!")
        print("💡 Check ESP32-CAM firmware and network configuration")
        return
    
    # Step 3: Test common ESP32-CAM endpoints
    common_endpoints = [
        f"http://{ip}/stream",
        f"http://{ip}:81/stream", 
        f"http://{ip}/mjpg/1",
        f"http://{ip}/cam",
        f"http://{ip}/video",
        f"http://{ip}:8080/stream"
    ]
    
    working_endpoints = []
    
    for endpoint in common_endpoints:
        success, response = test_http_endpoint(endpoint, timeout=15)
        if success:
            working_endpoints.append(endpoint)
    
    if not working_endpoints:
        print("\n❌ No working HTTP endpoints found!")
        print("💡 Try accessing the ESP32-CAM web interface directly in browser")
        return
    
    print(f"\n✅ Found {len(working_endpoints)} working endpoint(s):")
    for endpoint in working_endpoints:
        print(f"   - {endpoint}")
    
    # Step 4: Test OpenCV compatibility
    print(f"\n🔍 Testing OpenCV compatibility...")
    for endpoint in working_endpoints:
        print(f"\nTesting: {endpoint}")
        if test_cv2_stream(endpoint):
            print(f"✅ This endpoint works with OpenCV!")
            print(f"💡 Use this URL in your violence detection script: {endpoint}")
        else:
            print(f"❌ This endpoint doesn't work with OpenCV")
    
    # Step 5: Generate fixed code
    if working_endpoints:
        print(f"\n🛠️  RECOMMENDED FIXES:")
        print("-" * 30)
        
        # Find the best endpoint (prefer /stream)
        best_endpoint = None
        for endpoint in working_endpoints:
            if '/stream' in endpoint:
                best_endpoint = endpoint
                break
        
        if not best_endpoint:
            best_endpoint = working_endpoints[0]
        
        print(f"1. Use this URL: {best_endpoint}")
        print(f"2. Update your violence_detection.py script")
        print(f"3. Consider adding longer timeouts")
        
        # Show code modification
        print(f"\n📝 Code modification needed:")
        print(f"   Replace the ESP32-CAM connection part with:")
        print(f"   stream_url = '{best_endpoint}'")
        print(f"   cap = cv2.VideoCapture(stream_url)")
        print(f"   cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)")

if __name__ == "__main__":
    main()