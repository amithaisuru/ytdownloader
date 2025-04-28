# YouTube Downloader

## Overview

The YouTube Downloader is a Flask-based web application that enables users to download audio and video content from YouTube in various formats and qualities. It supports single video/audio downloads, playlist downloads, audio trimming, and video muting. The application is deployed using Gunicorn and managed with Supervisor for process monitoring and automatic restarts, making it suitable for shared hosting environments.

This README provides an overview for developers and users, including setup instructions, project structure, and guidelines for contributing to the project. For detailed developer documentation, refer to the [Project Documentation](docs/documentation.md) (to be created separately).

## Features

- **Audio Downloads**: Supports mp3, m4a, aac, and ogg formats with configurable bitrates.
- **Video Downloads**: Supports mp4, webm, and mkv formats with resolutions from 144p to 4K.
- **Playlist Support**: Downloads entire playlists as zipped archives.
- **Audio Trimming**: Allows users to specify start and end times for audio downloads (single videos only).
- **Video Muting**: Option to download videos without audio.
- **Responsive UI**: Modern, mobile-friendly interface with toast notifications.
- **Session Management**: Tracks downloads per user session with automatic cleanup of expired data.
- **Concurrent Downloads**: Handles multiple downloads using a thread pool.
- **Production-Ready**: Deployed with Gunicorn and Supervisor for reliability.

## Project Structure

```
/project_directory
│
├── /static
│   ├── style.css        # CSS styles for the front-end
│   └── script.js        # JavaScript for front-end interactivity
│
├── /templates
│   └── index.html       # Main HTML template for the user interface
│
├── /supervisord_utils
│   └── configure_supervisord.sh  # Script to configure Supervisor
│
├── app.py               # Main Flask application with routes and download logic
├── config.py            # Configuration settings (session lifetime, formats)
├── init_db.py           # Database initialization for tracking downloads
├── utils.py             # Utility functions for session cleanup and thread management
├── validations.py       # Input validation functions
├── how_to_run.txt       # Instructions for running the application
├── requirements.txt     # Python dependencies
├── server_init_start.sh # Initial setup and server start script
├── server_start.sh      # Script to start the server
├── server_stop.sh       # Script to stop the server
├── downloads/           # Directory for downloaded files (created at runtime)
├── flask_session/       # Directory for Flask session files (created at runtime)
├── logs/                # Directory for Supervisor logs (created at runtime)
└── venv/                # Virtual environment (created at runtime)
```

## Prerequisites

- **Operating System**: Ubuntu/Debian-based Linux (scripts use `apt`).
- **System Dependencies**:
  - Python 3.8+
  - FFmpeg
  - Supervisor
- **Permissions**: `sudo` access for installing packages and configuring Supervisor.

## Setup Instructions

### Initial Setup

1. Clone the repository:

```bash
git clone https://github.com/<your-username>/youtube-downloader.git
cd youtube-downloader
```

2. Run the initial setup script:

```bash
source server_init_start.sh
```

This script:
- Installs system dependencies (Python, FFmpeg, Supervisor).
- Creates a virtual environment (`venv/`).
- Installs Python dependencies from `requirements.txt`.
- Configures Supervisor for process management.
- Starts the application.

### Running the Application

- **Start the server**:

```bash
source server_start.sh
```

- **Stop the server**:

```bash
source server_stop.sh
```

- **Check status**:

```bash
sudo supervisorctl status youtube_downloader
```

### Accessing the Application

- Access at `http://<server-ip>:5000`.
- Ensure port 5000 is open in the firewall.

### Logs

- Supervisor logs: `logs/youtube_downloader.{out,err}.log`.
- Check logs for debugging.

## Dependencies

Defined in `requirements.txt`:

- `yt-dlp`: YouTube downloading library.
- `Flask==2.3.3`: Web framework.
- `Flask-Session==0.5.0`: Session management.
- `APScheduler==3.10.4`: Background task scheduling.
- `cachelib==0.9.0`: Cache support for Flask-Session.
- `gunicorn==22.0.0`: WSGI server for production.

Install dependencies manually (if not using `server_init_start.sh`):

```bash
pip install -r requirements.txt
```

## Deployment Notes

- **Gunicorn**: Runs the Flask app with a single worker. Adjust workers in `/etc/supervisor/conf.d/youtube_downloader.conf` for high traffic.
- **Supervisor**: Ensures automatic restarts on crashes. Monitor with `sudo supervisorctl`.
- **Virtual Environment**: Assumes `venv/` in the project root.
- **File Permissions**: Ensure write access to `downloads/`, `flask_session/`, and `logs/`.

## Contributing

We welcome contributions to enhance the YouTube Downloader. To contribute:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

### Development Guidelines

- **New Formats**: Update `config.py` and add handlers in `app.py` for new audio/video formats.
- **Performance**: Optimize threads (`utils.py`) and database queries for scale.
- **Security**: Sanitize inputs and file paths to prevent injection attacks.
- **Testing**: Test with various YouTube URLs (videos, playlists, Shorts) and edge cases.

Refer to the [Project Documentation](docs/documentation.md) for detailed developer guidelines.

## Known Limitations

- **High-Resolution Limits**: 4K (15 min) and 2K (30 min) duration limits to manage server load.
- **Playlist Trimming**: Audio trimming not supported for playlists.
- **FFmpeg Dependency**: Required for aac, ogg, and video muting.
- **Session Storage**: Filesystem-based storage may not scale for high traffic.

## Troubleshooting

- **Download Failures**:
  - Check `yt_dlp` errors in `logs/youtube_downloader.err.log`.
  - Verify FFmpeg (`ffmpeg -version`).
  - Ensure disk space in `downloads/`.
- **Database Issues**:
  - Confirm `downloads.db` is writable.
  - Use `db_lock` in `app.py` to avoid concurrency issues.
- **Supervisor Issues**:
  - Check logs (`logs/` or `/var/log/supervisor/`).
  - Restart Supervisor: `sudo supervisorctl reload`.

## Future Improvements

- Cloud storage integration (e.g., AWS S3).
- Job queue system (e.g., Celery).
- User authentication for download history.
- Real-time progress updates via WebSockets.
- Dockerization for portability.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.