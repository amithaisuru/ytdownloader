import re

import yt_dlp


def is_valid_url(url):
    """Validate if the URL is a proper YouTube URL, including Shorts."""
    if not url or not isinstance(url, str):
        return False, "URL is required and must be a string"
    
    youtube_regex = (
        r'^(https?://)?(www\.)?'
        r'(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/playlist\?list=|youtube\.com/shorts/)'
        r'[^\s<>"]+$'
    )
    if not re.match(youtube_regex, url):
        return False, "Invalid YouTube URL format"
    
    # Check if URL is accessible
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return False, "Could not retrieve video or playlist information"
        return True, None
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"

def is_valid_time_format(time_str):
    """Validate if the time string is in HH:MM:SS or MM:SS format."""
    if not time_str:
        return True, None  # Time is optional
    time_regex = r'^(\d{1,2}:\d{2}(:\d{2})?|\d{1,2}:\d{2})$'
    if not re.match(time_regex, time_str):
        return False, "Time must be in MM:SS or HH:MM:SS format"
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            if minutes > 59 or seconds > 59:
                return False, "Minutes and seconds must be less than 60"
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            if minutes > 99 or seconds > 59:
                return False, "Minutes must be less than 100 and seconds less than 60"
        return True, None
    except ValueError:
        return False, "Invalid time format"

def is_playlist(url):
    """Check if the URL is a playlist."""
    return 'playlist' in url.lower() or 'list=' in url
