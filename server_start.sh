#!/bin/bash

# Check if virtual environment is already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Virtual environment not active, activating..."
    source ./venv/bin/activate
else
    echo "Virtual environment already active: $VIRTUAL_ENV"
fi

# Run the application
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start youtube_downloader
sudo supervisorctl status youtube_downloader