SESSION_LIFETIME = 60*60  # 1h for testing

AUDIO_FORMATS = {
    'mp3': [64, 128, 192, 256, 320],
    'm4a': [128],
    'aac': [96, 128, 192],
    'ogg': [64, 128, 192, 256]
}

VIDEO_FORMATS = ['mp4', 'webm', 'mkv']
RESOLUTIONS = {
    '4k': '2160', '2k': '1440', '1080p': '1080', '720p': '720',
    '480p': '480', '360p': '360', '240p': '240', '144p': '144'
}