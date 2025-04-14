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

from flask_session import Session
from init_db import DB_PATH

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 30  # 1 day

def cleanup_expired_sessions():
    expiration = datetime.datetime.now() - datetime.timedelta(seconds=30)
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT session_id, file_path FROM downloads WHERE created_at < ?',
                (expiration,)
            )
            sessions_to_delete = set()
            for row in cursor.fetchall():
                session_id, file_path = row
                sessions_to_delete.add(session_id)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            for session_id in sessions_to_delete:
                session_dir = os.path.join('downloads', session_id)
                if os.path.exists(session_dir):
                    import shutil
                    try:
                        shutil.rmtree(session_dir)
                    except Exception:
                        pass
            conn.execute('DELETE FROM downloads WHERE created_at < ?', (expiration,))
            conn.commit()

    # Also check flask_session folder for expired sessions
    import glob
    session_dir = 'flask_session'
    if os.path.exists(session_dir):
        for session_file in glob.glob(os.path.join(session_dir, 'sess_*')):
            try:
                file_mtime = os.path.getmtime(session_file)
                if (datetime.datetime.now() - datetime.datetime.fromtimestamp(file_mtime)).total_seconds() > 30:
                    session_id = None
                    with open(session_file, 'rb') as f:
                        import pickle
                        data = pickle.load(f)
                        session_id = data.get('session_id')
                    os.remove(session_file)
                    if session_id:
                        session_dir = os.path.join('downloads', session_id)
                        if os.path.exists(session_dir):
                            import shutil
                            shutil.rmtree(session_dir)
            except Exception:
                pass

Session(app)
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_expired_sessions, trigger="interval", seconds=10)
scheduler.start()

AUDIO_FORMATS = {
    'mp3': [64, 128, 192, 256, 320],
    'm4a': [128],
    'aac': [96, 128, 192],
    'ogg': [64, 128, 192, 256]
}

VIDEO_FORMATS = ['mp4', 'webm', 'mkv']
RESOLUTIONS = {
    '4k': '2160', '2k': '1440', '1080p': '1080', '720p': '720',
    '480p': '480', '360p': '360', '244p': '240', '144p': '144'
}


# Threading setup
executor = ThreadPoolExecutor(max_workers=4)
db_lock = threading.Lock()

def is_playlist(url):
    return 'playlist' in url.lower() or 'list=' in url

def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def update_status(download_id, status, file_path=None):
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

def cleanup_expired_sessions():
    expiration = datetime.datetime.now() - datetime.timedelta(seconds=30)
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT session_id, file_path FROM downloads WHERE created_at < ?',
                (expiration,)
            )
            sessions_to_delete = set()
            for row in cursor.fetchall():
                session_id, file_path = row
                sessions_to_delete.add(session_id)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            for session_id in sessions_to_delete:
                session_dir = os.path.join('downloads', session_id)
                if os.path.exists(session_dir):
                    import shutil
                    try:
                        shutil.rmtree(session_dir)
                    except Exception:
                        pass
            conn.execute('DELETE FROM downloads WHERE created_at < ?', (expiration,))
            conn.commit()

    # Also check flask_session folder for expired sessions
    import glob
    session_dir = 'flask_session'
    if os.path.exists(session_dir):
        for session_file in glob.glob(os.path.join(session_dir, 'sess_*')):
            try:
                file_mtime = os.path.getmtime(session_file)
                if (datetime.datetime.now() - datetime.datetime.fromtimestamp(file_mtime)).total_seconds() > 30:
                    session_id = None
                    with open(session_file, 'rb') as f:
                        import pickle
                        data = pickle.load(f)
                        session_id = data.get('session_id')
                    os.remove(session_file)
                    if session_id:
                        session_dir = os.path.join('downloads', session_id)
                        if os.path.exists(session_dir):
                            import shutil
                            shutil.rmtree(session_dir)
            except Exception:
                pass

@app.route('/')
def home():
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
    url = request.form.get('url')
    format_type = request.form.get('format')
    bitrate = request.form.get('bitrate')
    start_time = request.form.get('start_time', '')
    end_time = request.form.get('end_time', '')

    if not url or not format_type or not bitrate:
        return jsonify({'error': 'Missing required fields'}), 400
    if format_type not in AUDIO_FORMATS or int(bitrate) not in AUDIO_FORMATS[format_type]:
        return jsonify({'error': 'Invalid format or bitrate'}), 400

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
    url = request.form.get('url')
    format_type = request.form.get('format')
    resolution = request.form.get('resolution')
    mute = request.form.get('mute', 'off') == 'on'

    if not url or not format_type or not resolution:
        return jsonify({'error': 'Missing required fields'}), 400
    if format_type not in VIDEO_FORMATS or resolution not in RESOLUTIONS:
        return jsonify({'error': 'Invalid format or resolution'}), 400

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
    update_status(download_id, 'Downloading')
    try:
        if format_type == 'aac':
            handle_aac_download(download_id, url, bitrate, start_time, end_time, user_dir)
        elif format_type == 'ogg':
            handle_ogg_download(download_id, url, bitrate, start_time, end_time, user_dir)
        else:
            handle_standard_audio_download(download_id, url, format_type, bitrate, start_time, end_time, user_dir)
    except Exception as e:
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_aac_download(download_id, url, bitrate, start_time, end_time, user_dir):
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

        subprocess.run(ffmpeg_cmd, check=True)

        if not os.path.exists(aac_path):
            raise Exception(f"Conversion failed: {aac_path} not found")

        update_status(download_id, 'Completed', aac_path)
    except Exception as e:
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_ogg_download(download_id, url, bitrate, start_time, end_time, user_dir):
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

        subprocess.run(ffmpeg_cmd, check=True)

        if not os.path.exists(ogg_path):
            raise Exception(f"Conversion failed: {ogg_path} not found")

        update_status(download_id, 'Completed', ogg_path)
    except Exception as e:
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_standard_audio_download(download_id, url, format_type, bitrate, start_time, end_time, user_dir):
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
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_playlist_download(download_id, session_id, url, format_type, bitrate, user_dir):
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
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_single_video_download(download_id, session_id, url, format_type, resolution, mute, user_dir):
    update_status(download_id, 'Downloading')
    try:
        ydl_opts = {
            'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]' if not mute else f'bestvideo[height<={RESOLUTIONS[resolution]}]',
            'merge_output_format': format_type,
            'outtmpl': os.path.join(user_dir, '%(title)s.%(ext)s'),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            duration = info.get('duration', 0)
            if resolution == '4k' and duration > 15 * 60:
                raise Exception("4K videos are limited to 15 minutes")
            if resolution == '2k' and duration > 30 * 60:
                raise Exception("2K videos are limited to 30 minutes")
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                raise Exception(f"File not found: {filename}")
        
        update_status(download_id, 'Completed', filename)
    except Exception as e:
        update_status(download_id, 'Error: ' + str(e))
        raise

def handle_playlist_video_download(download_id, session_id, url, format_type, resolution, mute, user_dir):
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_items = ydl.extract_info(url, download=True)
            if resolution in ['4k', '2k'] and playlist_items and 'entries' in playlist_items:
                for entry in playlist_items['entries']:
                    if entry:
                        duration = entry.get('duration', 0)
                        if resolution == '4k' and duration > 15 * 60:
                            raise Exception(f"Video '{entry.get('title', 'Unknown')}' exceeds 15-minute limit for 4K")
                        if resolution == '2k' and duration > 30 * 60:
                            raise Exception(f"Video '{entry.get('title', 'Unknown')}' exceeds 30-minute limit for 2K")

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
        update_status(download_id, 'Error: ' + str(e))
        raise

@app.route('/status/<download_id>')
def check_status(download_id):
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT file_path FROM downloads WHERE download_id = ?', (download_id,))
        result = cursor.fetchone()
        if result and result[0] and os.path.exists(result[0]):
            return send_file(result[0], as_attachment=True)
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)