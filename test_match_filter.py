import yt_dlp

def clean_title(info, *args, **kwargs):
    if info.get('title'):
        info['title'] = info['title'].replace('|', '-').replace('/', '-')
    return None

opts = {
    'quiet': True,
    'match_filter': clean_title,
    'outtmpl': 'test_%(title)s.%(ext)s'
}
ydl = yt_dlp.YoutubeDL(opts)
info = {'id': '1', 'title': 'A/B|C:D', 'ext': 'mp4'}
print("FILENAME:", ydl.prepare_filename(info))
