#!/usr/bin/env python3
import gradio as gr
import os
import librosa
import tempfile
import shutil
import datetime
from typing import TypeAlias, Tuple, Any
from music_video_cutter import analyze_beats, create_music_video

print(librosa.__version__)

VideoFilesInput : TypeAlias = Any
StatusResult : TypeAlias = Tuple[str, str]


def process_video(mp3_file : str, video_files : VideoFilesInput, cut_intensity : float, start_time : float, end_time : float, output_filename : str, direction : str, playback_speed_str: str) -> StatusResult:
    temp_dir = tempfile.mkdtemp()

    video_paths = []
    if video_files:
        files_list = video_files if isinstance(video_files, list) else [video_files]
        for video_file in files_list:
            if video_file:
                dest_path = os.path.join(temp_dir, os.path.basename(video_file))
                shutil.copy(video_file, dest_path)
                video_paths.append(dest_path)

    if len(video_paths) == 0:
        shutil.rmtree(temp_dir)
        return None, 'Error: No valid video files uploaded'

    #create output folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, 'output')
    os.makedirs(output_folder, exist_ok=True)

    #define filename, output, temp output
    name, ext = os.path.splitext(output_filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}{ext}"
    output_path = os.path.join(output_folder, filename)
    temp_output = os.path.join(tempfile.gettempdir(), filename)

    if playback_speed_str == 'Half Speed':
        speed_factor = 0.5
    elif playback_speed_str == 'Double Speed':
        speed_factor = 2.0
    else: # 'Normal Speed'
        speed_factor = 1.0

    cut_intensity_int = int(cut_intensity)

    end_time_value = None
    if end_time > 0:
        end_time_value = end_time
        
    beat_times, _, _ = analyze_beats(
        mp3_file,
        start_time=start_time,
        end_time=end_time_value
    )

    result_path = create_music_video(
        mp3_file,
        video_paths,
        beat_times,
        cut_intensity_int, # Übergebe den Integer-Wert
        output_file=temp_output,
        start_time=start_time,
        end_time=end_time_value,
        direction=direction,
        speed_factor=speed_factor
    )

    #move video to output
    shutil.move(result_path, output_path)

    # Aktualisiere die Statusmeldung, um "beats" statt "bass beats" zu sagen
    beats_used = len(beat_times[::cut_intensity_int])
    status_msg = f"Successfully created video with {beats_used} cuts from {len(beat_times)} detected beats."

    shutil.rmtree(temp_dir)

    return output_path, status_msg


def create_ui() -> gr.Blocks:
    app = gr.Blocks(title='Music Video Cutter')
    with app:
        gr.Markdown('''
        # Music Video Cutter

        Create dynamic music videos that cut on the bass beats of your audio track.
        Upload an MP3 file and multiple video clips, and the tool will automatically
        create a video that changes scenes in sync with the music's bass.
        ''')

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown('### Input Settings')

                mp3_input = gr.File(
                    label='MP3 Audio File',
                    file_types=['.mp3', '.MP3'],
                    type='filepath'
                )

                video_input = gr.File(
                    label='Video Files (MP4)',
                    file_count='multiple',
                    file_types=['.mp4', '.MP4'],
                    type='filepath'
                )

                with gr.Group():
                    gr.Markdown('### Processing Options')

                    cut_intensity = gr.Slider(
                        minimum=1,
                        maximum=16,
                        value=4,
                        step=1,
                        label='Cut Interval (Beats)',
                        info='Number of beats until next cut.'
                    )

                    direction = gr.Radio(
                        choices=['forward', 'backward', 'random'],
                        value='random',
                        label='Video Direction',
                        info='Forward: normal playback | Backward: reverse | Random: mix of forward/backward'
                    )

                    playback_speed = gr.Radio(
                        choices=['Normal Speed', 'Half Speed', 'Double Speed'],
                        value='Normal Speed',
                        label='Video Playback Speed',
                        info='Play all video clips at normal, half, or double speed.'
                    )

                    with gr.Row():
                        start_time = gr.Number(
                            value=0,
                            minimum=0,
                            label='Start Time (seconds)',
                            info='Where to start in the audio'
                        )

                        end_time = gr.Number(
                            value=0,
                            minimum=0,
                            label='End Time (seconds)',
                            info='Where to end (0 = full duration)'
                        )

                    output_filename = gr.Textbox(
                        value='music_video.mp4',
                        label='Base Output Filename',
                        info='Base name for the generated video file. A timestamp will be added.'
                    )

                process_btn = gr.Button('🎵 Create Music Video 🎬', variant='primary')

            with gr.Column(scale=1):
                gr.Markdown('### Output')

                status_output = gr.Textbox(
                    label='Status',
                    interactive=False,
                    value='Ready to process...'
                )

                video_output = gr.Video(
                    label='Generated Music Video',
                    interactive=False
                )

                gr.Markdown('''
                ### Tips:
                - Upload multiple short video clips for best results
                - Adjust the bass threshold if cuts are too frequent or too sparse
                - Use start/end times to process only a portion of the song
                - Videos will be randomly selected and cut to match the beat
                - Try different direction modes: forward for normal, backward for dramatic effect, or random for mixed forward/backward clips
                ''')

        process_btn.click(
            fn=process_video,
            inputs=[
                mp3_input,
                video_input,
                cut_intensity,
                start_time,
                end_time,
                output_filename,
                direction,
                playback_speed
            ],
            outputs=[video_output, status_output]
        )

    return app


if __name__ == '__main__':
    app = create_ui()
    app.launch()
