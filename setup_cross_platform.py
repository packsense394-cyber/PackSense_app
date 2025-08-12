#!/usr/bin/env python3
"""
Cross-platform setup script for PackSense
Automatically configures the environment for Windows, macOS, Linux, and mobile compatibility
"""

import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
import shutil
from pathlib import Path

def print_status(message, status="INFO"):
    """Print status message with color coding"""
    colors = {
        "INFO": "\033[94m",    # Blue
        "SUCCESS": "\033[92m", # Green
        "WARNING": "\033[93m", # Yellow
        "ERROR": "\033[91m",   # Red
        "RESET": "\033[0m"     # Reset
    }
    print(f"{colors.get(status, colors['INFO'])}[{status}] {message}{colors['RESET']}")

def get_system_info():
    """Get system information"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    print_status(f"Detected system: {system} {machine}", "INFO")
    return system, machine

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_status("Python 3.8+ is required", "ERROR")
        return False
    
    print_status(f"Python version: {version.major}.{version.minor}.{version.micro}", "SUCCESS")
    return True

def install_pip_packages():
    """Install required pip packages"""
    print_status("Installing Python packages...", "INFO")
    
    packages = [
        "flask==2.3.3",
        "selenium==4.15.2",
        "pandas==2.0.3",
        "numpy==1.24.3",
        "openpyxl==3.1.2",
        "requests==2.31.0",
        "pillow==10.0.1",
        "nltk==3.8.1",
        "scikit-learn==1.3.0",
        "mlxtend==0.22.0",
        "apscheduler==3.10.4",
        "webdriver-manager==4.0.1"
    ]
    
    for package in packages:
        try:
            print_status(f"Installing {package}...", "INFO")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print_status(f"Successfully installed {package}", "SUCCESS")
        except subprocess.CalledProcessError as e:
            print_status(f"Failed to install {package}: {e}", "ERROR")
            return False
    
    return True

def download_chromedriver(system, machine):
    """Download and install ChromeDriver"""
    print_status("Setting up ChromeDriver...", "INFO")
    
    # ChromeDriver version mapping (update as needed)
    chromedriver_versions = {
        "windows": {
            "x86_64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_win32.zip",
            "amd64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_win32.zip"
        },
        "darwin": {
            "x86_64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_mac64.zip",
            "arm64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_mac_arm64.zip"
        },
        "linux": {
            "x86_64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_linux64.zip",
            "amd64": "https://chromedriver.storage.googleapis.com/119.0.6045.105/chromedriver_linux64.zip"
        }
    }
    
    # Get the appropriate URL
    if system not in chromedriver_versions:
        print_status(f"Unsupported system: {system}", "ERROR")
        return False
    
    if machine not in chromedriver_versions[system]:
        print_status(f"Unsupported architecture: {machine}", "ERROR")
        return False
    
    url = chromedriver_versions[system][machine]
    filename = url.split('/')[-1]
    
    try:
        # Download ChromeDriver
        print_status(f"Downloading ChromeDriver from {url}...", "INFO")
        urllib.request.urlretrieve(url, filename)
        
        # Extract the archive
        print_status("Extracting ChromeDriver...", "INFO")
        if filename.endswith('.zip'):
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall('.')
        elif filename.endswith('.tar.gz'):
            with tarfile.open(filename, 'r:gz') as tar_ref:
                tar_ref.extractall('.')
        
        # Move to appropriate location
        chromedriver_name = "chromedriver.exe" if system == "windows" else "chromedriver"
        
        # Make executable on Unix systems
        if system != "windows":
            os.chmod(chromedriver_name, 0o755)
        
        # Clean up downloaded file
        os.remove(filename)
        
        print_status("ChromeDriver setup completed successfully", "SUCCESS")
        return True
        
    except Exception as e:
        print_status(f"Failed to setup ChromeDriver: {e}", "ERROR")
        return False

def setup_nltk_data():
    """Download required NLTK data"""
    print_status("Setting up NLTK data...", "INFO")
    
    try:
        import nltk
        
        # Download required NLTK resources
        resources = ['wordnet', 'omw-1.4', 'vader_lexicon']
        
        for resource in resources:
            try:
                print_status(f"Downloading NLTK resource: {resource}", "INFO")
                nltk.download(resource, quiet=True)
                print_status(f"Successfully downloaded {resource}", "SUCCESS")
            except Exception as e:
                print_status(f"Failed to download {resource}: {e}", "WARNING")
        
        return True
        
    except ImportError:
        print_status("NLTK not available, skipping NLTK data setup", "WARNING")
        return False

def create_directories():
    """Create necessary directories"""
    print_status("Creating directories...", "INFO")
    
    directories = [
        "static",
        "templates",
        "logs"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print_status(f"Created directory: {directory}", "SUCCESS")
        except Exception as e:
            print_status(f"Failed to create directory {directory}: {e}", "ERROR")
            return False
    
    return True

def create_config_file():
    """Create configuration file"""
    print_status("Creating configuration file...", "INFO")
    
    config_content = """# PackSense Cross-Platform Configuration

# Server settings
HOST = "0.0.0.0"
PORT = 5009
DEBUG = True

# Chrome settings
CHROME_HEADLESS = True
CHROME_WINDOW_SIZE = "1920,1080"

# Mobile settings
MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"

# File paths
STATIC_FOLDER = "static"
TEMPLATES_FOLDER = "templates"
LOGS_FOLDER = "logs"

# Cross-platform compatibility
ENABLE_MOBILE_OPTIMIZATION = True
ENABLE_DARK_MODE = True
ENABLE_TOUCH_SUPPORT = True
"""
    
    try:
        with open("config_cross_platform.py", "w") as f:
            f.write(config_content)
        print_status("Configuration file created successfully", "SUCCESS")
        return True
    except Exception as e:
        print_status(f"Failed to create configuration file: {e}", "ERROR")
        return False

def create_startup_scripts():
    """Create startup scripts for different platforms"""
    print_status("Creating startup scripts...", "INFO")
    
    # Windows batch file
    windows_script = """@echo off
echo Starting PackSense Cross-Platform Server...
python app_cross_platform.py
pause
"""
    
    # Unix shell script
    unix_script = """#!/bin/bash
echo "Starting PackSense Cross-Platform Server..."
python3 app_cross_platform.py
"""
    
    try:
        # Create Windows script
        with open("start_packsense.bat", "w") as f:
            f.write(windows_script)
        
        # Create Unix script
        with open("start_packsense.sh", "w") as f:
            f.write(unix_script)
        
        # Make Unix script executable
        if platform.system() != "Windows":
            os.chmod("start_packsense.sh", 0o755)
        
        print_status("Startup scripts created successfully", "SUCCESS")
        return True
        
    except Exception as e:
        print_status(f"Failed to create startup scripts: {e}", "ERROR")
        return False

def create_readme():
    """Create README file with setup instructions"""
    print_status("Creating README file...", "INFO")
    
    readme_content = """# PackSense Cross-Platform Setup

## Overview
PackSense is now compatible with Windows, macOS, Linux, and mobile devices.

## Quick Start

### Windows
1. Double-click `start_packsense.bat`
2. Or run: `python app_cross_platform.py`

### macOS/Linux
1. Run: `./start_packsense.sh`
2. Or run: `python3 app_cross_platform.py`

### Mobile Access
1. Start the server on your computer
2. Find your computer's IP address
3. On your mobile device, go to: `http://[YOUR_IP]:5009`

## Features
- ✅ Cross-platform compatibility
- ✅ Mobile-responsive interface
- ✅ Touch-friendly controls
- ✅ Dark mode support
- ✅ Automatic ChromeDriver setup
- ✅ NLTK data management

## Requirements
- Python 3.8+
- Chrome browser
- Internet connection

## Troubleshooting

### ChromeDriver Issues
If you encounter ChromeDriver issues:
1. Make sure Chrome browser is installed
2. Run: `python setup_cross_platform.py` to reinstall

### Mobile Access Issues
1. Check firewall settings
2. Ensure both devices are on the same network
3. Try using the mobile-optimized interface

## Support
For issues, check the logs in the `logs` directory.
"""
    
    try:
        with open("README_CROSS_PLATFORM.md", "w") as f:
            f.write(readme_content)
        print_status("README file created successfully", "SUCCESS")
        return True
    except Exception as e:
        print_status(f"Failed to create README file: {e}", "ERROR")
        return False

def main():
    """Main setup function"""
    print_status("Starting PackSense Cross-Platform Setup", "INFO")
    print_status("=" * 50, "INFO")
    
    # Check system
    system, machine = get_system_info()
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install packages
    if not install_pip_packages():
        return False
    
    # Setup ChromeDriver
    if not download_chromedriver(system, machine):
        return False
    
    # Setup NLTK data
    setup_nltk_data()
    
    # Create directories
    if not create_directories():
        return False
    
    # Create configuration
    if not create_config_file():
        return False
    
    # Create startup scripts
    if not create_startup_scripts():
        return False
    
    # Create README
    if not create_readme():
        return False
    
    print_status("=" * 50, "INFO")
    print_status("PackSense Cross-Platform Setup Completed Successfully!", "SUCCESS")
    print_status("You can now run the application using:", "INFO")
    
    if system == "windows":
        print_status("  start_packsense.bat", "INFO")
        print_status("  or: python app_cross_platform.py", "INFO")
    else:
        print_status("  ./start_packsense.sh", "INFO")
        print_status("  or: python3 app_cross_platform.py", "INFO")
    
    print_status("For mobile access, use your device's IP address", "INFO")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
