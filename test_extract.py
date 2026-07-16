import yt_dlp
def clean_title(info, *args, **kwargs):
    if info.get('title'):
        info['title'] = info['title'].replace('|', '-').replace('/', '-')
    return None

opts = {'quiet': True, 'match_filter': clean_title, 'outtmpl': 'test_%(title)s.%(ext)s'}
ydl = yt_dlp.YoutubeDL(opts)
info = ydl.extract_info('https://www.youtube.com/watch?v=4AJwwoz7o6I', download=False)
print("FILENAME:", ydl.prepare_filename(info))
