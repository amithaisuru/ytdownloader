# YouTube Downloader Project Documentation

## Overview

The YouTube Downloader is a Flask-based web application designed to allow users to download audio and video content from YouTube in various formats and qualities. It supports single video/audio downloads, playlist downloads, audio trimming, and video muting. The application is deployed using Gunicorn with 4 workers and managed with Supervisor for process monitoring and automatic restarts, making it suitable for shared hosting environments.

This documentation is intended for developers who will maintain or extend the application. It provides a comprehensive guide to the project structure, setup, deployment, and guidelines for further development.

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

## Key Components

### 1. Configuration (`config.py`)

Defines application settings:

- **SESSION_LIFETIME**: Session duration (default: 1 hour, 3600 seconds).
- **AUDIO_FORMATS**: Dictionary of supported audio formats (mp3, m4a, aac, ogg) with available bitrates.
- **VIDEO_FORMATS**: List of supported video formats (mp4, webm, mkv).
- **RESOLUTIONS**: Dictionary mapping resolution names (e.g., 4k, 1080p) to pixel heights.

### 2. Database (`init_db.py`)

Uses SQLite (`downloads.db`) to track downloads. The `downloads` table includes:

- `download_id`: Unique identifier for each download (UUID).
- `session_id`: User session identifier (UUID).
- `url`: YouTube URL.
- `status`: Download status (Pending, Downloading, Completed, Error).
- `format_type`: Selected format (e.g., mp3, mp4).
- `bitrate_or_res`: Bitrate (audio) or resolution (video).
- `file_path`: Path to the downloaded file.
- `created_at`: Timestamp of download initiation.

The `init_db()` function creates the table if it does not exist.

### 3. Utilities (`utils.py`)

Provides helper functions:

- **cleanup_expired_sessions()**: Deletes expired session data and files based on `SESSION_LIFETIME`. Cleans database entries, downloaded files, and Flask session files.
- **get_safe_thread_count()**: Determines the number of threads for concurrent downloads (default: 2, max: 16, configurable via `THREAD_COUNT` environment variable).

### 4. Validations (`validations.py`)

Contains input validation functions:

- **is_valid_url(url)**: Validates YouTube URLs (videos, Shorts, playlists) and checks accessibility using `yt_dlp`.
- **is_valid_time_format(time_str)**: Ensures time strings are in `HH:MM:SS` or `MM:SS` format.
- **is_playlist(url)**: Identifies playlist URLs.

### 5. Main Application (`app.py`)

The Flask application handles HTTP requests and download processing:

- **Routes**:
  - `/`: Renders the home page (`index.html`) with format and resolution options.
  - `/download_audio`: Processes audio download requests.
  - `/download_video`: Processes video download requests.
  - `/status/<download_id>`: Returns the status of a download.
  - `/download/<download_id>`: Serves the downloaded file.

- **Download Logic**:
  - Uses `yt_dlp` for downloading YouTube content.
  - Supports audio (mp3, m4a, aac, ogg) and video (mp4, webm, mkv) formats.
  - Handles single files and playlists (zipped for playlists).
  - Uses FFmpeg for audio trimming (mp3, m4a) and format conversion (aac, ogg).
  - Implements duration limits for high-resolution videos (15 min for 4K, 30 min for 2K).
  - Supports muting videos.
  - Uses `ThreadPoolExecutor` for concurrent downloads.
  - Tracks status in SQLite database with thread-safe operations (`db_lock`).

- **Session Management**:
  - Uses Flask-Session with filesystem storage (`flask_session/`).
  - Assigns a unique `session_id` per user session.
  - Cleans expired sessions using APScheduler (every 10 seconds).

### 6. Front-End (`index.html`, `style.css`, `script.js`)

- **index.html**:
  - Provides a tabbed interface for audio and video downloads.
  - Includes forms for URL, format, bitrate/resolution, audio trimming, and video muting.
  - Uses Jinja2 to populate options from `AUDIO_FORMATS`, `VIDEO_FORMATS`, and `RESOLUTIONS`.

- **style.css**:
  - Defines a responsive, modern design with CSS variables for colors and transitions.
  - Uses Font Awesome icons and Google Fonts (Inter).
  - Includes mobile-friendly media queries.

- **script.js**:
  - Manages tab switching (`openTab`).
  - Updates bitrate options dynamically (`updateBitrate`).
  - Displays toast notifications (`showToast`).
  - Handles form submissions and polls download status via Fetch API.

### 7. Deployment Scripts

- **server_init_start.sh**:
  - Installs system dependencies (Python, FFmpeg, Supervisor).
  - Creates a virtual environment (`venv/`).
  - Installs Python dependencies from `requirements.txt`.
  - Configures Supervisor for process management.
  - Starts the application.

- **server_start.sh**:
  - Activates the virtual environment if not already active.
  - Starts the application using Supervisor.

- **server_stop.sh**:
  - Stops the application via Supervisor.
  - Deactivates the virtual environment if active.

- **supervisord_utils/configure_supervisord.sh**:
  - Creates a Supervisor configuration file (`/etc/supervisor/conf.d/youtube_downloader.conf`).
  - Configures Gunicorn to run `app:app` on `0.0.0.0:5000` with 4 workers (`-w 4`) for improved concurrency.
  - Sets up logging to `logs/youtube_downloader.{out,err}.log`.

### 8. Requirements (`requirements.txt`)

Lists Python dependencies:

- `yt-dlp`: For downloading YouTube content.
- `Flask==2.3.3`: Web framework.
- `Flask-Session==0.5.0`: Session management.
- `APScheduler==3.10.4`: Background task scheduling.
- `cachelib==0.9.0`: Cache support for Flask-Session.
- `gunicorn==22.0.0`: WSGI server for production.

## Setup Instructions

### Prerequisites

- **Operating System**: Ubuntu/Debian-based Linux (scripts use `apt` and assume a Linux environment).
- **System Dependencies**:
  - Python 3.8+
  - FFmpeg
  - Supervisor
- **Permissions**: `sudo` access for installing packages and configuring Supervisor.

### Initial Setup

1. Clone the project repository.
2. Navigate to the project directory.
3. Run the initial setup script:

```bash
source server_init_start.sh
```

This script:
- Installs system dependencies.
- Creates and activates a virtual environment (`venv/`).
- Installs Python dependencies.
- Installs and configures Supervisor.
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

- The application runs on `http://<server-ip>:5000`.
- Ensure port 5000 is open in the firewall.

### Logs

- Supervisor logs: `logs/youtube_downloader.{out,err}.log`.
- Check logs for debugging issues.

## Deployment Notes

- **Gunicorn**: Runs the Flask app in production mode with 4 workers (`-w 4`) for improved concurrency, as specified in `/etc/supervisor/conf.d/youtube_downloader.conf`. Adjust the worker count based on server resources (e.g., CPU cores).
- **Supervisor**: Ensures the application restarts on crashes. Monitor status with `sudo supervisorctl`.
- **Virtual Environment**: All scripts assume `venv/` is in the project root. Ensure it is not deleted.
- **File Permissions**: Ensure the application user has write access to `downloads/`, `flask_session/`, and `logs/`.

## Development Guidelines

### Extending the Application

1. **Adding New Formats**:
   - Update `AUDIO_FORMATS` or `VIDEO_FORMATS` in `config.py`.
   - For audio formats requiring FFmpeg (e.g., aac, ogg), add a handler in `app.py` (see `handle_aac_download`).
   - For standard formats, ensure `yt_dlp` supports the codec in `FFmpegExtractAudio`.

2. **Adding New Resolutions**:
   - Update `RESOLUTIONS` in `config.py`.
   - Adjust duration limits in `check_video_duration` if needed.

3. **Enhancing Validation**:
   - Modify `validations.py` for new URL patterns or rules.
   - Test `yt_dlp` compatibility with new YouTube features.

4. **Improving Performance**:
   - Increase `NUM_OF_THREADS` in `app.py` for high traffic, but monitor server resources.
   - Optimize database queries in `utils.py` and `app.py` for large datasets.
   - Consider caching `yt_dlp` metadata for frequently accessed URLs.

5. **Front-End Enhancements**:
   - Add form fields in `index.html` and handle them in `script.js` and `app.py`.
   - Maintain consistency with `style.css` design language.
   - Enhance toast notifications for detailed feedback.

6. **Deployment Enhancements**:
   - Add environment variables for configuration (e.g., port, worker count, log level).
   - Use a reverse proxy (e.g., Nginx) for load balancing and SSL.
   - Configure log rotation for `logs/` directory.

### Best Practices

- **Thread Safety**: Use `db_lock` for all SQLite operations to prevent race conditions.
- **Error Handling**: Ensure download functions update database status on errors.
- **File Management**: Verify file existence before serving in `/download/<download_id>`.
- **Session Cleanup**: Test `cleanup_expired_sessions` for edge cases (e.g., corrupted files).
- **Security**:
  - Sanitize user inputs and file paths (`sanitize_filename` in `yt_dlp` helps).
  - Restrict Supervisor configuration access (`/etc/supervisor/conf.d/`).
- **Testing**:
  - Test with various YouTube URLs (videos, playlists, Shorts).
  - Verify edge cases (invalid URLs, long videos, large playlists).

### Known Limitations

- **High-Resolution Limits**: 4K (15 min) and 2K (30 min) duration limits to manage server load.
- **Playlist Trimming**: Audio trimming not supported for playlists.
- **FFmpeg Dependency**: Required for aac, ogg, and video muting; ensure availability.
- **Worker Configuration**: Fixed at 4 workers; may need adjustment for different server capacities.

## Maintenance Tasks

- **Update Dependencies**: Regularly update `requirements.txt` packages and `yt_dlp` for security and compatibility.
- **Monitor FFmpeg**: Ensure FFmpeg compatibility with conversion commands.
- **Database Maintenance**: Check `downloads.db`
- **Session Cleanup**: Verify `cleanup_expired_sessions` removes all expired data.
- **Log Management**: Monitor `logs/` for size and configure rotation if needed.
- **Supervisor**: Periodically check `sudo supervisorctl status` for uptime.