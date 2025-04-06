import os

import yt_dlp
from flask import Flask, render_template, request, send_file

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download_audio', methods=['POST'])
def download_audio():
    url = request.form.get('url')
    if not url:
        return "No URL provided. Please enter a valid YouTube link.", 400
    
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
    }
    try:
        os.makedirs('downloads', exist_ok=True)
        #download and convert he audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True) # Download and get video info
            # Fix the filename (yt-dlp might use .webm but we need .mp3)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3')
            response = send_file(filename, as_attachment=True)
            # os.remove(filename)
            return response
    except Exception as e:
        return f"Error downloading audio: {str(e)}", 500

@app.route('/download_video', methods=['POST'])
def download_video():
    url = request.form.get('url')
    if not url:
        return "No URL provided. Please enter a valid YouTube link.", 400
    
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',  # 720p video + audio
        'merge_output_format': 'mp4', 
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
    