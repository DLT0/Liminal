import yt_dlp
opts = {
    'quiet': True,
    'replace_in_metadata': [
        ('title', r'[\\/*?:"<>|]', '_')
    ],
    'outtmpl': 'test_%(title)s.%(ext)s'
}
ydl = yt_dlp.YoutubeDL(opts)
info = {'id': '1', 'title': 'A/B|C:D?E"F - Tiếng Việt', 'ext': 'mp4'}
ydl.process_info(info)
print("FILENAME:", ydl.prepare_filename(info))
