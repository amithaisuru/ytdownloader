import datetime
import os
import re
import sqlite3
import subprocess
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request, send_file, session
from yt_dlp.utils import sanitize_filename

from config import AUDIO_FORMATS, RESOLUTIONS, SESSION_LIFETIME, VIDEO_FORMATS
from flask_session import Session
from init_db import DB_PATH
from utils import cleanup_expired_sessions, get_safe_thread_count
from validations import *

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_LIFETIME 

Session(app)
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_expired_sessions, trigger="interval", seconds=10)
scheduler.start()

# Threading setup
NUM_OF_THREADS = get_safe_thread_count()
executor = ThreadPoolExecutor(max_workers=NUM_OF_THREADS)
db_lock = threading.Lock()

def get_timestamp():
    """Generate a timestamp for file naming."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def update_status(download_id, status, file_path=None):
    """Update the download status in the database."""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            if file_path:
                conn.execute(
                    'UPDATE downloads SET status = ?, file_path = ? WHERE download_id = ?',
                    (status, file_path, download_id)
                )
            else:
                conn.execute(
                    'UPDATE downloads SET status = ? WHERE download_id = ?',
                    (status, download_id)
                )
            conn.commit()

def check_video_duration(url, resolution, is_playlist=False):
    """
    Check if video(s) duration exceeds limits for 4K (15 min) or 2K (30 min).
    Returns a tuple: (is_valid, error_message).
    """
    limits = {'4k': 15 * 60, '2k': 30 * 60}  # in seconds
    if resolution not in limits:
        return True, None

    try:
        ydl_opts = {'extract_flat': is_playlist, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if is_playlist:
                if not info or 'entries' not in info:
                    return False, "Could not retrieve playlist information"
                for entry in info['entries']:
                    if entry:
                        duration = entry.get('duration', 0)
                        if duration > limits[resolution]:
                            return False, f"Video '{entry.get('title', 'Unknown')}' exceeds {limits[resolution]//60}-minute limit for {resolution}"
            else:
                duration = info.get('duration', 0)
                if duration > limits[resolution]:
                    return False, f"Video exceeds {limits[resolution]//60}-minute limit for {resolution}"
        return True, None
    except Exception as e:
        return False, f"Error checking duration: {str(e)}"

@app.route('/')
def home():
    """Render the home page with available formats and resolutions."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session.permanent = True
    return render_template(
        'index.html',
        audio_formats=AUDIO_FORMATS,
        video_formats=VIDEO_FORMATS,
        resolutions=RESOLUTIONS.keys(),
        session_id=session['session_id']
    )

@app.route('/download_audio', methods=['POST'])
def download_audio():
    """Handle audio download requests with input validation."""
    url = request.form.get('url')
    format_type = request.form.get('format')
    bitrate = request.form.get('bitrate')
    start_time = request.form.get('start_time', '')
    end_time = request.form.get('end_time', '')

    # Validate inputs
    is_valid, error = is_valid_url(url)
    if not is_valid:
        return jsonify({'error': error}), 400

    is_valid, error = is_valid_time_format(start_time)
    if not is_valid:
        return jsonify({'error': f"Invalid start time: {error}"}), 400

    is_valid, error = is_valid_time_format(end_time)
    if not is_valid:
        return jsonify({'error': f"Invalid end time: {error}"}), 400

    # Check if end_time is after start_time if both are provided
    if start_time and end_time:
        try:
            def to_seconds(time_str):
                parts = time_str.split(':')
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                return int(parts[0]) * 60 + int(parts[1])
            
            if to_seconds(end_time) <= to_seconds(start_time):
                return jsonify({'error': "End time must be after start time"}), 400
        except ValueError:
            return jsonify({'error': "Error parsing time values"}), 400

    session_id = session.get('session_id', str(uuid.uuid4()))
    session['session_id'] = session_id
    session.permanent = True
    download_id = str(uuid.uuid4())

    user_dir = os.path.join('downloads', session_id)
    os.makedirs(user_dir, exist_ok=True)

    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO downloads (download_id, session_id, url, status, format_type, bitrate_or_res, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (download_id, session_id, url, 'Pending', format_type, bitrate, datetime.datetime.now())
            )
            conn.commit()

    if is_playlist(url):
        if start_time or end_time:
            return jsonify({'error': 'Trimming not supported for playlists'}), 400
        executor.submit(handle_playlist_download, download_id, session_id, url, format_type, bitrate, user_dir)
    else:
        executor.submit(handle_single_audio_download, download_id, session_id, url, format_type, bitrate, start_time, end_time, user_dir)

    return jsonify({'download_id': download_id, 'status': 'Pending'})

@app.route('/download_video', methods=['POST'])
def download_video():
    """Handle video download requests with input validation."""
    url = request.form.get('url')
    format_type = request.form.get('format')
    resolution = request.form.get('resolution')
    mute = request.form.get('mute', 'off') == 'on'

    # Validate inputs
    is_valid, error = is_valid_url(url)
    if not is_valid:
        return jsonify({'error': error}), 400

    # Check video duration before proceeding
    is_valid, error_message = check_video_duration(url, resolution, is_playlist(url))
    if not is_valid:
        return jsonify({'error': error_message}), 400

    session_id = session.get('session_id', str(uuid.uuid4()))
    session['session_id'] = session_id
    session.permanent = True
    download_id = str(uuid.uuid4())

    user_dir = os.path.join('downloads', session_id)
    os.makedirs(user_dir, exist_ok=True)

    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO downloads (download_id, session_id, url, status, format_type, bitrate_or_res, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (download_id, session_id, url, 'Pending', format_type, resolution, datetime.datetime.now())
            )
            conn.commit()

    if is_playlist(url):
        executor.submit(handle_playlist_video_download, download_id, session_id, url, format_type, resolution, mute, user_dir)
    else:
        executor.submit(handle_single_video_download, download_id, session_id, url, format_type, resolution, mute, user_dir)

    return jsonify({'download_id': download_id, 'status': 'Pending'})

def handle_single_audio_download(download_id, session_id, url, format_type, bitrate, start_time, end_time, user_dir):
    """Handle downloading a single audio file."""
    update_status(download_id, 'Downloading')
    try:
        if format_type == 'aac':
            handle_aac_download(download_id, url, bitrate, start_time, end_time, user_dir)
        elif format_type == 'ogg':
            handle_ogg_download(download_id, url, bitrate, start_time, end_time, user_dir)
        else:
            handle_standard_audio_download(download_id, url, format_type, bitrate, start_time, end_time, user_dir)
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_aac_download(download_id, url, bitrate, start_time, end_time, user_dir):
    """Handle AAC audio download with FFmpeg conversion."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            safe_title = sanitize_filename(info['title'])
        
        download_path = os.path.join(user_dir, f'{safe_title}.webm')
        aac_path = os.path.join(user_dir, f'{safe_title}.aac')

        ydl_opts = {
            'format': 'bestaudio[ext=webm]/bestaudio',
            'outtmpl': download_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        ffmpeg_cmd = ['ffmpeg', '-y', '-i', download_path]
        if start_time:
            ffmpeg_cmd.extend(['-ss', start_time])
        if end_time:
            ffmpeg_cmd.extend(['-to', end_time])
        ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', bitrate + 'k', '-f', 'adts', aac_path])

        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        if not os.path.exists(aac_path):
            raise Exception(f"Conversion failed: {aac_path} not found")

        update_status(download_id, 'Completed', aac_path)
    except subprocess.CalledProcessError as e:
        update_status(download_id, f'Error: FFmpeg failed - {e.stderr}')
        raise
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_ogg_download(download_id, url, bitrate, start_time, end_time, user_dir):
    """Handle OGG audio download with FFmpeg conversion."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            safe_title = sanitize_filename(info['title'])
        
        download_path = os.path.join(user_dir, f'{safe_title}.webm')
        ogg_path = os.path.join(user_dir, f'{safe_title}.ogg')

        ydl_opts = {
            'format': 'bestaudio[ext=webm]/bestaudio',
            'outtmpl': download_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        ffmpeg_cmd = ['ffmpeg', '-y', '-i', download_path]
        if start_time:
            ffmpeg_cmd.extend(['-ss', start_time])
        if end_time:
            ffmpeg_cmd.extend(['-to', end_time])
        ffmpeg_cmd.extend(['-c:a', 'libvorbis', '-b:a', bitrate + 'k', ogg_path])

        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        if not os.path.exists(ogg_path):
            raise Exception(f"Conversion failed: {ogg_path} not found")

        update_status(download_id, 'Completed', ogg_path)
    except subprocess.CalledProcessError as e:
        update_status(download_id, f'Error: FFmpeg failed - {e.stderr}')
        raise
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_standard_audio_download(download_id, url, format_type, bitrate, start_time, end_time, user_dir):
    """Handle standard audio download (mp3, m4a)."""
    try:
        ydl_opts = {
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': format_type,
                'preferredquality': bitrate,
            }],
            'outtmpl': os.path.join(user_dir, '%(title)s.%(ext)s'),
        }
        if start_time and end_time:
            ydl_opts['postprocessor_args'] = ['-ss', start_time, '-to', end_time]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', f'.{format_type}').replace('.m4a', f'.{format_type}')
            if not os.path.exists(filename):
                raise Exception(f"File not found: {filename}")
        
        update_status(download_id, 'Completed', filename)
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_playlist_download(download_id, session_id, url, format_type, bitrate, user_dir):
    """Handle downloading an audio playlist."""
    update_status(download_id, 'Downloading')
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if not playlist_info:
                raise Exception("Could not retrieve playlist information")
            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_info.get('title', 'playlist'))

        timestamp = get_timestamp()
        playlist_dir = os.path.join(user_dir, f"{playlist_title}_{timestamp}")
        os.makedirs(playlist_dir, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'aac' if format_type == 'aac' else 'vorbis' if format_type == 'ogg' else format_type,
                'preferredquality': bitrate,
            }],
            'outtmpl': f'{playlist_dir}/%(title)s.%(ext)s',
            'ignoreerrors': True,
        }
        if format_type == 'aac':
            ydl_opts['postprocessor_args'] = ['-f', 'adts']

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        zip_path = os.path.join(user_dir, f"{playlist_title}_{timestamp}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(playlist_dir):
                for file in files:
                    expected_ext = '.aac' if format_type == 'aac' else '.ogg' if format_type == 'ogg' else f'.{format_type}'
                    if file.endswith(expected_ext):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, user_dir)
                        zipf.write(file_path, arcname)

        update_status(download_id, 'Completed', zip_path)
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_single_video_download(download_id, session_id, url, format_type, resolution, mute, user_dir):
    """Handle downloading a single video file."""
    update_status(download_id, 'Downloading')
    try:
        ydl_opts = {
            'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]' if not mute else f'bestvideo[height<={RESOLUTIONS[resolution]}]',
            'merge_output_format': format_type,
            'outtmpl': os.path.join(user_dir, '%(title)s.%(ext)s'),
        }
        if mute:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': format_type,
            }]
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if mute:
                filename = os.path.splitext(filename)[0] + f'.{format_type}'
            if not os.path.exists(filename):
                raise Exception(f"File not found: {filename}")
        
        update_status(download_id, 'Completed', filename)
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise

def handle_playlist_video_download(download_id, session_id, url, format_type, resolution, mute, user_dir):
    """Handle downloading a video playlist."""
    update_status(download_id, 'Downloading')
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if not playlist_info:
                raise Exception("Could not retrieve playlist information")
            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_info.get('title', 'playlist'))

        timestamp = get_timestamp()
        playlist_dir = os.path.join(user_dir, f"{playlist_title}_{timestamp}")
        os.makedirs(playlist_dir, exist_ok=True)

        ydl_opts = {
            'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]' if not mute else f'bestvideo[height<={RESOLUTIONS[resolution]}]',
            'merge_output_format': format_type,
            'outtmpl': f'{playlist_dir}/%(title)s.%(ext)s',
            'ignoreerrors': True,
        }
        if mute:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': format_type,
            }]
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        zip_path = os.path.join(user_dir, f"{playlist_title}_{timestamp}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(playlist_dir):
                for file in files:
                    if file.endswith(f'.{format_type}'):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, user_dir)
                        zipf.write(file_path, arcname)

        update_status(download_id, 'Completed', zip_path)
    except Exception as e:
        update_status(download_id, f'Error: {str(e)}')
        raise
    
@app.route('/status/<download_id>')
def check_status(download_id):
    """Check the status of a download."""
    cleanup_expired_sessions()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT status, file_path FROM downloads WHERE download_id = ?', (download_id,))
        result = cursor.fetchone()
        if result:
            status, file_path = result
            return jsonify({'download_id': download_id, 'status': status, 'file_path': file_path})
        return jsonify({'error': 'Download not found'}), 404

@app.route('/download/<download_id>')
def download_file(download_id):
    """Serve the downloaded file."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT file_path FROM downloads WHERE download_id = ?', (download_id,))
        result = cursor.fetchone()
        if result and result[0] and os.path.exists(result[0]):
            return send_file(result[0], as_attachment=True)
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)