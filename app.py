import datetime
import os
import re
import tempfile
import zipfile

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

AUDIO_FORMATS = {
    'mp3': [64, 128, 192, 256, 320],  # MP3 supports these bitrates
    'm4a': [128],                     # M4A uses 128 kbps (AAC codec)
    # 'aac': [96, 128, 192],            # AAC options
    # 'ogg': [64, 128, 192, 256]        # OGG options
}

VIDEO_FORMATS = ['mp4', 'webm', 'mkv']
RESOLUTIONS = {
    '4k': '2160', '2k': '1440', '1080p': '1080', '720p': '720',
    '480p': '480', '360p': '360', '244p': '240', '144p': '144'
}

@app.route('/')
def home():
    return render_template(
        'index.html',
        audio_formats=AUDIO_FORMATS,
        video_formats=VIDEO_FORMATS,
        resolutions = RESOLUTIONS.keys()
    )

def is_playlist(url):
    """Check if the URL is a playlist or contains a playlist identifier."""
    return 'playlist' in url or 'list=' in url

def get_timestamp():
    """Get formatted timestamp for folder naming."""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S")

@app.route('/download_audio', methods=['POST'])
def download_audio():
    url = request.form.get('url')
    format_type = request.form.get('format')
    bitrate = request.form.get('bitrate')
    start_time = request.form.get('start_time', '')
    end_time = request.form.get('end_time', '')

    if not url or not format_type or not bitrate:
        return "Missing required fields. Please fill out all options.", 400

    if format_type not in AUDIO_FORMATS or int(bitrate) not in AUDIO_FORMATS[format_type]:
        return "Invalid format or bitrate selected.", 400
    
    # Create downloads directory if it doesn't exist
    os.makedirs('downloads', exist_ok=True)

    # Check if URL is a playlist
    if is_playlist(url):
        if start_time or end_time:
            return "Trimming (start/end time) is not supported for playlists. Please remove trim settings or use a single video URL.", 400
 
        # If it's a playlist, we'll download all videos as separate audio files and zip them
        return handle_playlist_download(url, format_type, bitrate)
    else:
        # If it's a single video, proceed with standard download
        return handle_single_audio_download(url, format_type, bitrate, start_time, end_time)

def handle_single_audio_download(url, format_type, bitrate, start_time='', end_time=''):
    """Handle download of a single audio file."""
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_type,
            'preferredquality': bitrate,
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }

    if start_time and end_time:
        ydl_opts['postprocessors'][0]['key'] = 'FFmpegExtractAudio'
        ydl_opts['postprocessor_args'] = ['-ss', start_time, '-to', end_time]

    try:
        # Download and convert the audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)  # Download and get video info
            # Adjust file name
            filename = ydl.prepare_filename(info).replace('.webm', f'.{format_type}').replace('.m4a', f'.{format_type}')
            response = send_file(filename, as_attachment=True)
            # os.remove(filename)  # Uncomment to remove file after sending
            return response
    except Exception as e:
        return f"Error downloading audio: {str(e)}", 500

def handle_playlist_download(url, format_type, bitrate):
    """Handle download of a playlist as audio files."""
    try:
        # First, extract playlist information to get the playlist title
        with yt_dlp.YoutubeDL({'extract_flat': True}) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if not playlist_info:
                return "Could not retrieve playlist information.", 500
            
            playlist_title = playlist_info.get('title', 'playlist')
            # Clean filename to avoid issues with filesystem
            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
    except Exception as e:
        return f"Error retrieving playlist information: {str(e)}", 500

    # Create a directory for this playlist
    timestamp = get_timestamp()
    folder_name = f"{playlist_title}_{timestamp}"
    playlist_dir = os.path.join('downloads', folder_name)
    os.makedirs(playlist_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_type,
            'preferredquality': bitrate,
        }],
        'outtmpl': f'downloads/{folder_name}/%(title)s.%(ext)s',
        'ignoreerrors': True,  # Skip videos that cannot be downloaded
    }

    try:
        # Download all videos in the playlist
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        # Create a zip file of all downloaded audio files
        zip_path = os.path.join('downloads', f"{folder_name}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(playlist_dir):
                for file in files:
                    if file.endswith(f'.{format_type}'):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, 'downloads')
                        zipf.write(file_path, arcname)

        # Send the zip file
        response = send_file(zip_path, as_attachment=True)
        # Clean up files - uncomment to enable cleanup
        # import shutil
        # shutil.rmtree(playlist_dir)
        # os.remove(zip_path)
        return response

    except Exception as e:
        return f"Error downloading playlist: {str(e)}", 500

@app.route('/download_video', methods=['POST'])
def download_video():
    url = request.form.get('url')
    format_type = request.form.get('format')
    resolution = request.form.get('resolution')
    mute = request.form.get('mute', 'off') == 'on'

    if not url or not format_type or not resolution:
        return "Missing required fields. Please fill out all options.", 400
    if format_type not in VIDEO_FORMATS or resolution not in RESOLUTIONS:
        return "Invalid format selected.", 400
    
    if is_playlist(url):
        return handle_playlist_video_download(url, format_type, resolution, mute)
    else:
        return handle_single_video_download(url, format_type, resolution, mute)
        
def handle_single_video_download(url, format_type, resolution, mute):
    ydl_opts = {
        'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]',
        'merge_output_format': format_type,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }

    if mute:
        ydl_opts['format'] = f'bestvideo[height<={RESOLUTIONS[resolution]}]/best[height<={RESOLUTIONS[resolution]}]'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': format_type,
        }]
    
    try:
        os.makedirs('downloads', exist_ok=True)
        #download and convert the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True) # Download and get video info
            duration = info.get('duration', 0)  # Get video duration in seconds

            # Enforce duration restrictions
            if resolution == '4k' and duration > 15 * 60:  # 15 minutes
                return "4K videos are limited to 15 minutes.", 400
            if resolution == '2k' and duration > 30 * 60:  # 30 minutes
                return "2K videos are limited to 30 minutes.", 400
            
            filename = ydl.prepare_filename(info)
            response = send_file(filename, as_attachment=True)
            # os.remove(filename)
            return response
        
    except Exception as e:
        return f"Error downloading video: {str(e)}", 500

def handle_playlist_video_download(url, format_type, resolution, mute):
    #ectract plalist info and get playlist title
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True}) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if not playlist_info:
                return "Could not retrieve playlist information.", 500
            
            playlist_title = playlist_info.get('title', 'playlist')
            # Clean filename to avoid issues with filesystem
            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
    except Exception as e:
        return f"Error retrieving playlist information: {str(e)}", 500
    
    # Create a directory for this playlist
    timestamp = get_timestamp()
    folder_name = f"{playlist_title}_{timestamp}"
    playlist_dir = os.path.join('downloads', folder_name)
    os.makedirs(playlist_dir, exist_ok=True)

    #configure yt-dlp options
    ydl_opts = {
        'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]',
        'merge_output_format': format_type,
        'outtmpl': f'downloads/{folder_name}/%(title)s.%(ext)s',
        'ignoreerrors': True,  # Skip videos that cannot be downloaded
    }

    if mute:
        ydl_opts['format'] = f'bestvideo[height<={RESOLUTIONS[resolution]}]/best[height<={RESOLUTIONS[resolution]}]'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': format_type,
        }]
    
    try:
        #download all videos
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_items = ydl.extract_info(url, download=True)

            #chec duration constraints
            if resolution in ['4k', '2k'] and playlist_items and 'entries' in playlist_items:
                for entry in playlist_items['entries']:
                    if entry:
                        duration = entry.get('duration', 0)
                        if resolution == '4k'  and duration > 15 * 60:
                            return f"Video '{entry.get('title', 'Unknown')}' exceeds the 15-minute limit for 4K resolution.", 400
                        if resolution == '2k' and duration > 30 * 60:
                            return f"Video '{entry.get('title', 'Unknown')}' exceeds the 30-minute limit for 2K resolution.", 400
            
        # Create a zip file of all downloaded video files
        zip_path = os.path.join('downloads', f"{folder_name}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(playlist_dir):
                for file in files:
                    if file.endswith(f'.{format_type}'):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, 'downloads')
                        zipf.write(file_path, arcname)
        
        #send the zip file
        response = send_file(zip_path, as_attachment=True)
        # Clean up files - uncomment to enable cleanup
        # import shutil
        # shutil.rmtree(playlist_dir)
        # os.remove(zip_path)
        return response
    
    except Exception as e:
        return f"Error downloading playlist: {str(e)}", 500
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)