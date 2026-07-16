import yt_dlp.utils
print("Default:", yt_dlp.utils.sanitize_filename("A/B|C:D?E\"F"))
print("Windows:", yt_dlp.utils.sanitize_filename("A/B|C:D?E\"F", restricted=False, is_id=False))
