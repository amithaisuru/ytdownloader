#!/bin/bash

# Check if working directory is provided
if [ -z "$1" ]; then
    echo "Error: Working directory not provided"
    exit 1
fi
working_directory="$1"

config_file_dir="/etc/supervisor/conf.d/youtube_downloader.conf"

#write config file
sudo tee "$config_file_dir" > /dev/null <<EOF
[program:youtube_downloader]
directory=$working_directory
command=$working_directory/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
autostart=true
autorestart=true
startretries=10
stderr_logfile=$working_directory/logs/youtube_downloader.err.log
stdout_logfile=$working_directory/logs/youtube_downloader.out.log
environment=PYTHONPATH="$working_directory"
user=$USER
EOF

echo "Config file created at: $config_file_dir"