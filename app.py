import os

import yt_dlp
from flask import Flask, render_template, request, send_file

app = Flask(__name__)

AUDIO_FORMATS = {
    'mp3': [64, 128, 192, 256, 320],  # MP3 supports these bitrates
    'm4a': [128],                     # M4A uses 128 kbps (AAC codec)
    'aac': [96, 128, 192],            # AAC options
    'ogg': [64, 128, 192, 256]        # OGG options
}

VIDEO_FORMATS = ['mp4', 'webm', 'mkv']

@app.route('/')
def home():
    return render_template('index.html', audio_formats=AUDIO_FORMATS, video_formats=VIDEO_FORMATS)

@app.route('/download_audio', methods=['POST'])
def download_audio():
    url = request.form.get('url')
    format_type = request.form.get('format')
    bitrate = request.form.get('bitrate')

    if not url or not format_type or not bitrate:
        return "Missing required fields. Please fill out all options.", 400

    if format_type not in AUDIO_FORMATS or int(bitrate) not in AUDIO_FORMATS[format_type]:
        return "Invalid format or bitrate selected.", 400
    
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_type,
            'preferredquality': bitrate,
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }
    try:
        os.makedirs('downloads', exist_ok=True)
        #download and convert he audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True) # Download and get video info
            # adjust file name
            filename = ydl.prepare_filename(info).replace('.webm', f'.{format_type}').replace('.m4a', f'.{format_type}')
            response = send_file(filename, as_attachment=True)
            # os.remove(filename)
            return response
    except Exception as e:
        return f"Error downloading audio: {str(e)}", 500

@app.route('/download_video', methods=['POST'])
def download_video():
    url = request.form.get('url')
    format_type = request.form.get('format')

    if not url or not format_type:
        return "Missing required fields. Please fill out all options.", 400
    if format_type not in VIDEO_FORMATS:
        return "Invalid format selected.", 400
    
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',  # 720p video + audio
        'merge_output_format': format_type, 
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }

    try:
        os.makedirs('downloads', exist_ok=True)
        #download and convert he audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True) # Download and get video info
            filename = ydl.prepare_filename(info)
            response = send_file(filename, as_attachment=True)
            # os.remove(filename)
            return response
    except Exception as e:
        return f"Error downloading video: {str(e)}", 500
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    