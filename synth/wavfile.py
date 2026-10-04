"""Write a mono 16-bit wav without extra dependencies."""

from __future__ import annotations

import wave

import numpy as np


def save_wav(path, audio, sr):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        return
    audio = np.clip(audio, -1.0, 1.0).copy()
    fade = min(64, audio.size // 2)
    if fade:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        audio[:fade] *= ramp
        audio[-fade:] *= ramp[::-1]
    pcm = (audio * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sr))
        handle.writeframes(pcm.tobytes())
