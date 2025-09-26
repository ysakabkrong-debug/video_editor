Python 3.13.7 (tags/v3.13.7:bcee1c3, Aug 14 2025, 14:06:58) [MSC v.1944 32 bit (Intel)] on win32
Enter "help" below or click "Help" above for more information.
>>> 
... 
... import os
... import uuid
... from flask import Flask, request, render_template_string, send_file
... from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip, ColorClip, AudioFileClip
... import moviepy.video.fx.all as vfx
... import whisper
... 
... UPLOAD_FOLDER = "uploads"
... OUTPUT_FOLDER = "outputs"
... os.makedirs(UPLOAD_FOLDER, exist_ok=True)
... os.makedirs(OUTPUT_FOLDER, exist_ok=True)
... 
... app = Flask(__name__)
... 
... # ===== HTML giao diện =====
... HTML = """
... <!DOCTYPE html>
... <html>
... <head>
...   <title>Mini Auto Video Editor</title>
... </head>
... <body style="font-family: sans-serif; padding:20px;">
...   <h2>🎬 Mini Auto Video Editor</h2>
...   <form action="/process" method="post" enctype="multipart/form-data">
...     <p>Upload video clips: <input type="file" name="videos" multiple required></p>
...     <p>Upload background music: <input type="file" name="music"></p>
...     <p>Title: <input type="text" name="title" value="Demo Video"></p>
...     <p><label><input type="checkbox" name="subtitles" value="1"> Thêm phụ đề tự động (Whisper)</label></p>
...     <button type="submit">Render Video</button>
...   </form>
... </body>
... </html>
... """
... 
... # ===== Xử lý clip =====
... def load_and_prepare(path, target_size=(1280,720), max_duration=6):
...     clip = VideoFileClip(path)
...     if clip.duration > max_duration:
...         clip = clip.subclip(0, max_duration)
...     clip = clip.resize(height=target_size[1])
...     if clip.w > target_size[0]:
...         clip = clip.crop(x_center=clip.w/2, width=target_size[0])
...     else:
        bg = ColorClip(size=target_size, color=(0,0,0)).set_duration(clip.duration)
        clip = CompositeVideoClip([bg, clip.set_position("center")])
    return clip.set_fps(30).fx(vfx.colorx, 1.02)

def make_title_clip(text, duration=3, w=1280, h=720):
    txt = TextClip(text, fontsize=60, font='Arial-Bold', color='white',
                   size=(w*0.9, None), method='caption').set_duration(duration)
    box = ColorClip(size=(w,h), color=(0,0,0)).set_opacity(0.6).set_duration(duration)
    return CompositeVideoClip([box, txt.set_position("center")])

def generate_subtitles(clip, model="tiny"):
    model = whisper.load_model(model)
    tmp = f"{uuid.uuid4().hex}.wav"
    clip.audio.write_audiofile(tmp, verbose=False, logger=None)
    result = model.transcribe(tmp, language="vi")
    os.remove(tmp)
    subs = []
    for seg in result["segments"]:
        subs.append(((seg["start"], seg["end"]), seg["text"]))
    gen = lambda txt: TextClip(txt, fontsize=36, color='yellow', stroke_color='black', stroke_width=2)
    from moviepy.editor import SubtitlesClip
    return SubtitlesClip(subs, gen)

# ===== Routes =====
@app.route("/")
def index():
    return HTML

@app.route("/process", methods=["POST"])
def process():
    # save uploaded files
    video_paths = []
    for f in request.files.getlist("videos"):
        path = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(path)
        video_paths.append(path)

    music_file = None
    if "music" in request.files:
        mf = request.files["music"]
        if mf.filename:
            music_file = os.path.join(UPLOAD_FOLDER, mf.filename)
            mf.save(music_file)

    title = request.form.get("title", "Demo Video")
    add_subs = request.form.get("subtitles") == "1"

    # build video
    clips = []
    for vp in video_paths:
        c = load_and_prepare(vp)
        if add_subs and c.audio is not None:
            try:
                subs = generate_subtitles(c)
                c = CompositeVideoClip([c, subs.set_pos(("center","bottom"))])
            except:
                pass
        clips.append(c)

    final = concatenate_videoclips(clips, method="compose")
    final = concatenate_videoclips([make_title_clip(title), final])

    if music_file:
        music = AudioFileClip(music_file).volumex(0.5)
        if music.duration < final.duration:
            from moviepy.audio.fx.all import audio_loop
            music = audio_loop(music, duration=final.duration)
        final = final.set_audio(music)

    out_name = f"{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(OUTPUT_FOLDER, out_name)
    final.write_videofile(out_path, codec="libx264", audio_codec="aac", fps=30, threads=4)

    return send_file(out_path, as_attachment=True, download_name="result.mp4")

if __name__ == "__main__":
