#!/bin/bash

# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source ./venv/bin/activate

# Install Python dependencies in the virtual environment
pip install --upgrade pip
pip install -r requirements.txt

# Run the application
python3 app.py