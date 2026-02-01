#!/usr/bin/env python3
import argparse
import os
import random
from functools import partial
from typing import TypeAlias, Tuple, List
import numpy as np
import librosa
from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips
from moviepy.video.fx.MultiplySpeed import MultiplySpeed
from pathlib import Path


AudioData : TypeAlias = np.ndarray
BeatTimes : TypeAlias = np.ndarray
VideoList : TypeAlias = List[str]


def reverse_time_transform(original_duration : float, fps : float, t : float) -> float:
    return max(0, min(original_duration - t - 1/fps, original_duration - 1/fps))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Create a music video with cuts synchronized to bass beats'
    )
    parser.add_argument(
        'mp3_file',
        type=str,
        help='Path to the input MP3 file'
    )
    parser.add_argument(
        'video_directory',
        type=str,
        help='Directory containing MP4 video files'
    )
    parser.add_argument(
        'cut_intensity',
        type=int,
        choices=[1, 2, 3],
        help='Cut intensity: 1 (every beat), 2 (every 2nd beat), 3 (every 3rd beat)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='output_music_video.mp4',
        help='Output video file path (default: output_music_video.mp4)'
    )
    parser.add_argument(
        '-d', '--duration',
        type=float,
        default=2.0,
        help='Default clip duration in seconds (default: 2.0)'
    )
    parser.add_argument(
        '-s', '--start-time',
        type=float,
        default=0.0,
        help='Start time in seconds for MP3 processing (default: 0.0)'
    )
    parser.add_argument(
        '-e', '--end-time',
        type=float,
        default=None,
        help='End time in seconds for MP3 processing (default: full duration)'
    )
    parser.add_argument(
        '--direction',
        type=str,
        choices=['forward', 'backward', 'random'],
        default='random',
        help='Video playback direction: forward (normal), backward (reverse), or random (mix of both) (default: random)'
    )

    return parser.parse_args()


def get_video_files(directory : str) -> VideoList:
    video_extensions = ['.mp4', '.MP4']
    video_files = []

    for ext in video_extensions:
        video_files.extend(Path(directory).glob(f'*{ext}'))

    if not video_files:
        raise ValueError(f'No MP4 files found in {directory}')

    return [str(f) for f in video_files]

# Ersetze die alte analyze_bass_beats Funktion mit dieser neuen Version
def analyze_beats(audio_file: str, start_time: float = 0.0, end_time: float = None):
    """
    Analysiert Beats, indem es das Beat-Tracking direkt mit einer
    Bass-fokussierten Onset-Kurve füttert. Das ist der robusteste Ansatz.
    """
    duration = None
    if end_time and end_time > start_time:
        duration = end_time - start_time

    y, sr = librosa.load(audio_file, sr=22050, offset=start_time, duration=duration)

    # --- Schritt 1: Erstelle eine Onset-Hüllkurve, die NUR auf Bass-Frequenzen basiert ---
    # Wir berechnen das Spektrogramm und isolieren die Bass-Energie.
    stft = librosa.stft(y)
    freqs = librosa.fft_frequencies(sr=sr)
    bass_band = (freqs >= 20) & (freqs <= 200)
    # Die Summe der Bass-Energie ist unsere Bass-spezifische Onset-Hüllkurve.
    bass_onset_env = np.sum(np.abs(stft[bass_band, :]), axis=0)

    # --- Schritt 2: Führe das Beat-Tracking mit unserer Bass-Hüllkurve durch ---
    # Wir sagen librosa: "Finde einen regelmäßigen Beat, aber orientiere dich
    # stark an den Spitzen in DIESER Bass-Kurve."
    # Das behebt das Problem der willkürlichen Schnitte.
    try:
        # Dieser Aufruf benötigt eine neuere librosa Version.
        tempo, beat_frames = librosa.beat.beat_track(onset_envelope=bass_onset_env, sr=sr, units='frames')
    except TypeError:
        # Fallback für ältere librosa Versionen
        print("Warning: Using fallback beat tracking due to older librosa version.")
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='frames')

    if tempo.size > 0:
        print(f"Detected tempo: {tempo[0]:.2f} BPM")
    else:
        print("Could not detect tempo.")
        return np.array([]), y, sr # Leeres Array zurückgeben, wenn nichts gefunden wurde

    # Konvertiere die Frame-Indizes in Zeitstempel
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)

    print(f"Returning {len(beat_times)} bass-focused, regular beat times.")
    
    return beat_times, y, sr


# KORRIGIERTE VERSION VON create_music_video
# In music_video_cutter.py
def create_music_video(mp3_file : str, video_files : VideoList, beat_times : BeatTimes, cut_intensity : int,
                      default_duration : float = 2.0, output_file : str = 'output_music_video.mp4',
                      start_time : float = 0.0, end_time : float = None, direction : str = 'random',
                      speed_factor: float = 1.0) -> str:
    """
    Erstellt ein Musikvideo, indem Videoclips passend zu den erkannten Beats geschnitten werden.
    Unterstützt variable Wiedergabegeschwindigkeit der Videoclips.
    """
    if len(beat_times) == 0:
        raise ValueError("No beats were detected. Cannot create video.")

    # Lade die Audiodatei und schneide sie basierend auf Start/Endzeit zu.
    full_audio = AudioFileClip(mp3_file)
    if end_time and end_time > start_time:
        audio = full_audio.subclipped(start_time, end_time)
    elif start_time > 0:
        audio = full_audio.subclipped(start_time)
    else:
        audio = full_audio
    
    audio_duration = audio.duration
    print(f"Processing audio segment of duration: {audio_duration:.2f} seconds.")

    # Wähle die Beats basierend auf der 'cut_intensity' aus.
    selected_beats = beat_times[::cut_intensity]

    # Stelle sicher, dass die Beat-Liste am Anfang (0) beginnt und am Ende (audio_duration) aufhört.
    if len(selected_beats) == 0 or selected_beats[0] > 0.1:
        selected_beats = np.insert(selected_beats, 0, 0)
    if selected_beats[-1] < audio_duration:
        selected_beats = np.append(selected_beats, audio_duration)

    clips = []
    videos_to_close = []
    target_size = None

    # Iteriere durch die Beat-Paare, um die Dauer für jeden Clip zu bestimmen.
    for i in range(len(selected_beats) - 1):
        # Die Zieldauer des Clips im finalen Video (synchron zum Beat).
        final_duration = selected_beats[i + 1] - selected_beats[i]
        
        # Berechne die benötigte Dauer des *Quell*-Videoclips.
        # Für halbe Geschwindigkeit (speed_factor=0.5) brauchen wir einen doppelt so langen Clip.
        required_source_duration = final_duration * speed_factor

        video_file = random.choice(video_files)
        video = VideoFileClip(video_file)
        videos_to_close.append(video)

        # Schneide einen zufälligen Ausschnitt aus dem Quellvideo in der benötigten Länge.
        if video.duration >= required_source_duration:
            max_start = video.duration - required_source_duration
            clip_start = random.uniform(0, max_start)
            clip = video.subclipped(clip_start, clip_start + required_source_duration)
        else:
            # Wenn das Quellvideo zu kurz ist, nimm das ganze Video.
            clip = video

        # Wende den Geschwindigkeitseffekt an.
        if speed_factor != 1.0:
            print(f"Applying speed factor {speed_factor} to clip {i+1}")
            speed_effect = MultiplySpeed(factor=speed_factor)
            clip = speed_effect.apply(clip)
            clip = clip.with_duration(final_duration)

        # Wende die Wiedergaberichtung (vorwärts, rückwärts, zufällig) an.
        if direction == 'backward':
            original_duration = clip.duration
            reverse_func = partial(reverse_time_transform, original_duration, clip.fps)
            clip = clip.time_transform(reverse_func)
            clip = clip.with_duration(original_duration)

        if direction == 'random':
            if random.choice([True, False]): # Wähle zufällig, ob rückwärts abgespielt wird
                original_duration = clip.duration
                reverse_func = partial(reverse_time_transform, original_duration, clip.fps)
                clip = clip.time_transform(reverse_func)
                clip = clip.with_duration(original_duration)

        # Passe die Größe der Videos an, damit sie alle gleich groß sind.
        if i == 0:
            target_size = clip.size
        if target_size and clip.size != target_size:
            clip = clip.resized(target_size)
            
        clips.append(clip)

    if not clips:
        raise ValueError('No valid video clips could be created')

    # Füge alle erstellten Clips zu einem einzigen Video zusammen.
    final_video = concatenate_videoclips(clips)
    
    # Füge die korrekt geschnittene Audiospur hinzu.
    final_video = final_video.with_audio(audio)

    # Stelle sicher, dass das finale Video nicht länger als die Audiospur ist.
    final_video = final_video.subclipped(0, min(final_video.duration, audio_duration))

    # Schreibe die finale Videodatei.
    final_video.write_videofile(
        output_file,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='temp-audio.m4a',
        remove_temp=True
    )

    # Gib die Ressourcen frei.
    final_video.close()
    audio.close()
    full_audio.close()
    for video in videos_to_close:
        video.close()

    return output_file


def main() -> None:
    args = parse_arguments()

    if not os.path.exists(args.mp3_file):
        raise FileNotFoundError('MP3 file not found: ' + args.mp3_file)

    if not os.path.isdir(args.video_directory):
        raise NotADirectoryError('Video directory not found: ' + args.video_directory)

    print('Analyzing audio file: ' + args.mp3_file)
    if args.end_time:
        print('Processing from ' + str(args.start_time) + 's to ' + str(args.end_time) + 's')
    if args.start_time > 0 and args.end_time is None:
        print('Processing from ' + str(args.start_time) + 's to end')

    beat_times, _, _ = analyze_beats(
        args.mp3_file,
        start_time=args.start_time,
        end_time=args.end_time
    )

    print(f'Found {len(beat_times)} beats')
    print(f'With cut intensity {args.cut_intensity}, will use {len(beat_times[::args.cut_intensity])} cuts')

    video_files = get_video_files(args.video_directory)
    print('Found ' + str(len(video_files)) + ' video files')

    video_files = get_video_files(args.video_directory)
    print(f'Found {len(video_files)} video files')

    print('Creating music video...')
    output_file = create_music_video(
        args.mp3_file,
        video_files,
        beat_times,
        args.cut_intensity,
        default_duration=args.duration,
        output_file=args.output,
        start_time=args.start_time,
        end_time=args.end_time,
        direction=args.direction
        # Beachte: Die Kommandozeilenversion hat keine Option für speed_factor,
        # also wird der Standardwert 1.0 verwendet.
    )

    print('Music video created successfully: ' + output_file)


if __name__ == '__main__':
    main()