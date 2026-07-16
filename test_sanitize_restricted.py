import yt_dlp.utils
print(yt_dlp.utils.sanitize_filename("A/B|C:D?E\"F - Tiếng Việt", restricted=True))
