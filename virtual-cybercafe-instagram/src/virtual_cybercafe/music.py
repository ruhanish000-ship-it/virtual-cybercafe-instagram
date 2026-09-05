from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 48_000


def _midi(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def _soft_clip(audio: np.ndarray) -> np.ndarray:
    return np.tanh(audio * 1.25) / np.tanh(1.25)


def generate_original_music(path: Path, duration: float = 18.0) -> Path:
    """Create an original, royalty-free corporate/tech instrumental bed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260903)
    length = int(duration * SAMPLE_RATE)
    t = np.arange(length, dtype=np.float64) / SAMPLE_RATE
    mix = np.zeros(length, dtype=np.float64)

    # Cmaj7 - Am7 - Fmaj7 - G6; four seconds per chord.
    chords = [
        (48, 52, 55, 59),
        (45, 48, 52, 55),
        (41, 45, 48, 52),
        (43, 47, 50, 52),
    ]
    chord_seconds = 4.0
    for chord_index, notes in enumerate(chords):
        start = chord_index * chord_seconds
        if start >= duration:
            break
        end = min(start + chord_seconds + 0.35, duration)
        indices = (t >= start) & (t < end)
        local_t = t[indices] - start
        attack = np.minimum(local_t / 0.65, 1.0)
        release = np.minimum((end - start - local_t) / 0.75, 1.0)
        envelope = np.clip(attack * release, 0.0, 1.0)
        for voice, note in enumerate(notes):
            frequency = _midi(note)
            phase = voice * 0.7
            pad = np.sin(2 * np.pi * frequency * local_t + phase)
            pad += 0.30 * np.sin(2 * np.pi * frequency * 2.0 * local_t + phase / 2)
            mix[indices] += 0.035 * envelope * pad

    # Light pluck melody at 120 BPM, deliberately deterministic and original.
    melody = [72, 76, 79, 76, 69, 72, 76, 72, 65, 69, 72, 69, 67, 71, 74, 79]
    beat = 0.5
    for index, note in enumerate(melody * math.ceil(duration / (len(melody) * beat))):
        start = index * beat
        if start >= duration:
            break
        note_length = min(0.42, duration - start)
        start_sample = int(start * SAMPLE_RATE)
        count = int(note_length * SAMPLE_RATE)
        local_t = np.arange(count) / SAMPLE_RATE
        envelope = np.exp(-local_t * 7.0) * np.minimum(local_t / 0.015, 1.0)
        freq = _midi(note)
        pluck = np.sin(2 * np.pi * freq * local_t) + 0.35 * np.sin(4 * np.pi * freq * local_t)
        mix[start_sample : start_sample + count] += 0.075 * envelope * pluck

    # Restrained kick, clap and hi-hat pattern.
    for beat_index in range(int(duration / beat) + 1):
        start = beat_index * beat
        start_sample = int(start * SAMPLE_RATE)
        if start_sample >= length:
            break
        count = min(int(0.20 * SAMPLE_RATE), length - start_sample)
        local_t = np.arange(count) / SAMPLE_RATE
        if beat_index % 2 == 0:
            kick = np.sin(2 * np.pi * (72 - 42 * local_t) * local_t) * np.exp(-local_t * 24)
            mix[start_sample : start_sample + count] += 0.10 * kick
        else:
            clap = rng.normal(0, 1, count) * np.exp(-local_t * 30)
            mix[start_sample : start_sample + count] += 0.018 * clap
        hat_count = min(int(0.06 * SAMPLE_RATE), length - start_sample)
        hat_t = np.arange(hat_count) / SAMPLE_RATE
        hat = rng.normal(0, 1, hat_count) * np.exp(-hat_t * 65)
        mix[start_sample : start_sample + hat_count] += 0.012 * hat

    fade_samples = min(int(0.8 * SAMPLE_RATE), length // 3)
    mix[:fade_samples] *= np.linspace(0, 1, fade_samples)
    mix[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    mix = _soft_clip(mix)
    peak = max(float(np.max(np.abs(mix))), 1e-9)
    mix = mix / peak * 0.78

    # A subtle stereo spread prevents the bed from sounding flat.
    delay = int(0.012 * SAMPLE_RATE)
    right = np.roll(mix, delay) * 0.93
    right[:delay] = 0
    stereo = np.column_stack((mix, right))
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return path

