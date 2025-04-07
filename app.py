import os

import yt_dlp
from flask import Flask, render_template, request, send_file

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
    
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_type,
            'preferredquality': bitrate,
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }

    if start_time and end_time and 'playlist' not in url.lower():
        ydl_opts['postprocessors'][0]['key'] = 'FFmpegExtractAudio'
        ydl_opts['postprocessor_args'] = ['-ss', start_time, '-to', end_time]

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
    resolution = request.form.get('resolution')
    mute = request.form.get('mute', 'off') == 'on'

    if not url or not format_type or not resolution:
        return "Missing required fields. Please fill out all options.", 400
    if format_type not in VIDEO_FORMATS or resolution not in RESOLUTIONS:
        return "Invalid format selected.", 400
    
    ydl_opts = {
        'format': f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]',
        'merge_output_format': format_type,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }

    if mute:
        ydl_opts['format'] = f'bestvideo[height<={RESOLUTIONS[resolution]}]+bestaudio/best[height<={RESOLUTIONS[resolution]}]'
    
    try:
        os.makedirs('downloads', exist_ok=True)
        #download and convert he audio
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
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    