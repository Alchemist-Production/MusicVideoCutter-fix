## 2024-05-23 - MoviePy Performance Optimization
**Learning:** Instantiating `VideoFileClip` inside a loop for the same file is highly inefficient as it re-opens the file and spawns ffmpeg/ffprobe processes each time.
**Action:** Cache `VideoFileClip` instances when reusing the same video source for multiple cuts.
