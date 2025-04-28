#!/bin/bash

working_directory=$(pwd)
echo "working directory detected: $working_directory"

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

#Install supervisord (crash autorestarting)
sudo apt install supervisor

#configure supervisord
mkdir -p logs
source supervisord_utils/configure_supervisord.sh "$working_directory"

# Run the application
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start youtube_downloader
sudo supervisorctl status youtube_downloader