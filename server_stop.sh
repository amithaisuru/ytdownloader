#!/bin/bash

# Stop the application
echo "Stopping youtube_downloader..."
sudo supervisorctl stop youtube_downloader
sudo supervisorctl status youtube_downloader

# Check if virtual environment is active and deactivate if necessary
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Virtual environment active: $VIRTUAL_ENV, deactivating..."
    deactivate
else
    echo "No virtual environment active, skipping deactivation."
fi