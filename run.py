#!/usr/bin/env python3
"""
PackSense - Intelligent Packaging Evaluation Platform
Run script for the Flask application
"""

import os
import sys
import signal
import subprocess
import time

def kill_process_on_port(port):
    """Kill any process running on the specified port"""
    try:
        result = subprocess.run(['lsof', '-ti', str(port)], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    subprocess.run(['kill', '-9', pid])
                    print(f"Killed process {pid} on port {port}")
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")

def main():
    port = 5009
    
    print("🚀 Starting PackSense - Intelligent Packaging Evaluation Platform")
    print("=" * 60)
    
    # Kill any existing process on the port
    print(f"Checking for existing processes on port {port}...")
    kill_process_on_port(port)
    
    # Wait a moment for the port to be freed
    time.sleep(1)
    
    try:
        # Import and run the Flask app
        from app import app
        print(f"✅ Application loaded successfully")
        print(f"🌐 Starting server on http://127.0.0.1:{port}")
        print(f"📱 Open your browser and navigate to the URL above")
        print("=" * 60)
        print("Press Ctrl+C to stop the server")
        print("=" * 60)
        
        app.run(debug=True, port=port, use_reloader=False, host='127.0.0.1')
        
    except ImportError as e:
        print(f"❌ Error importing application: {e}")
        print("Make sure all required files are present:")
        print("- app.py (main application)")
        print("- config.py (configuration)")
        print("- scraper.py (web scraping functions)")
        print("- nlp_utils.py (NLP utilities)")
        print("- templates/ (HTML templates)")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 