"""Engine checks that do not need a speaker."""

from __future__ import annotations

import sys
import time

import numpy as np

from synth.dsp import ATTACK, SUSTAIN, env_block
from synth.engine import SynthEngine
from synth.keys import LABELS, SEMI_COUNT, semi_from_event
from synth.params import quantize
from synth.presets import FACTORY_PRESETS


def _rms(audio):
    audio = np.asarray(audio, dtype=np.float64)
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio * audio)))


def _dry(engine):
    engine.analog = False
    engine.set_param("reverb_mix", 0)
    engine.set_param("delay_mix", 0)
    engine.set_param("chorus_mix", 0)
    engine.set_param("drive", 1)
    engine.set_param("filter_type", 3)


def test_quantize():
    assert quantize(61, 0, 0) == 61
    assert quantize(60, 0, 1) == 60
    assert quantize(61, 0, 1) == 60
    assert quantize(64, 0, 1) == 64
    assert quantize(66, 0, 3) in (64, 67)


def test_keys():
    for semi in range(SEMI_COUNT):
        assert semi in LABELS
    assert semi_from_event(90, "Hangul") == 0
    assert semi_from_event(81, "q") == 12
    assert semi_from_event(50, "2") == 13
    assert semi_from_event(0, "p") == 28


def test_envelope():
    env, level, stage = env_block(0.0, ATTACK, 44100, 44100, 0.05, 0.1, 0.5, 0.2)
    assert stage == SUSTAIN
    assert abs(level - 0.5) < 0.05
    assert env[-1] > 0.4


def test_pitch_and_silence():
    engine = SynthEngine()
    _dry(engine)
    engine.set_param("osc1_wave", 0)
    engine.set_param("osc1_level", 0.9)
    engine.set_param("osc2_level", 0)
    engine.set_param("amp_a", 0.001)
    engine.set_param("amp_d", 0.05)
    engine.set_param("amp_s", 1)
    engine.set_param("amp_r", 0.05)
    engine.set_param("volume", 0.9)
    assert _rms(engine.render(2048)) < 1e-4
    engine.note_down(69)
    for _ in range(8):
        engine.render(512)
    chunks = [engine.render(2048) for _ in range(20)]
    audio = np.concatenate(chunks)
    assert np.all(np.isfinite(audio))
    window = audio * np.hanning(audio.size)
    spec = np.abs(np.fft.rfft(window))
    freq = np.fft.rfftfreq(audio.size, 1.0 / engine.sr)
    peak = float(freq[int(np.argmax(spec[1:])) + 1])
    assert abs(peak - 440.0) < 6.0, peak
    engine.note_up(69)
    for _ in range(40):
        engine.render(512)
    assert _rms(engine.render(2048)) < 0.02


def test_poly_sustain_mono():
    engine = SynthEngine()
    _dry(engine)
    engine.set_param("amp_a", 0.001)
    engine.set_param("amp_s", 1)
    engine.set_param("amp_r", 0.05)
    engine.note_down(60)
    engine.note_down(64)
    engine.render(1024)
    held = [v for v in engine.voices if v.active and v.amp_stage < 3]
    assert len(held) == 2
    engine.set_sustain(True)
    engine.note_up(60)
    engine.note_up(64)
    assert _rms(engine.render(2048)) > 0.01
    engine.set_sustain(False)
    for _ in range(50):
        engine.render(512)
    assert _rms(engine.render(2048)) < 0.02

    engine.set_param("voice_mode", 2)
    engine.set_param("glide", 0.2)
    engine.note_down(60)
    for _ in range(20):
        engine.render(256)
    engine.note_down(67)
    assert engine.voices[0].note == 67
    assert engine.voices[0].amp_level > 0.4


def test_arp_and_presets():
    engine = SynthEngine()
    _dry(engine)
    engine.set_param("arp_on", 1)
    engine.set_param("arp_bpm", 120)
    engine.set_param("arp_div", 0)
    engine.set_param("arp_gate", 0.5)
    engine.set_param("amp_a", 0.001)
    engine.set_param("amp_d", 0.05)
    engine.set_param("amp_s", 0.8)
    engine.set_param("amp_r", 0.05)
    engine.arp_triggers = 0
    engine.note_down(60)
    engine.note_down(64)
    engine.note_down(67)
    blocks = int(engine.sr * 2 / 512)
    audio = np.concatenate([engine.render(512) for _ in range(blocks)])
    assert np.all(np.isfinite(audio))
    assert 3 <= engine.arp_triggers <= 6, engine.arp_triggers
    assert _rms(audio) > 0.01

    for name, preset in FACTORY_PRESETS:
        eng = SynthEngine()
        eng.analog = False
        eng.load(preset)
        eng.note_down(60)
        eng.note_down(64)
        eng.note_down(67)
        audio = np.concatenate([eng.render(512) for _ in range(120)])
        assert np.all(np.isfinite(audio)), name
        rms = _rms(audio)
        assert 0.004 < rms < 0.85, (name, rms)


def test_speed():
    engine = SynthEngine()
    engine.analog = False
    for note in (48, 52, 55, 60, 64, 67, 72, 76):
        engine.note_down(note)
    engine.render(512)
    started = time.perf_counter()
    loops = 80
    for _ in range(loops):
        engine.render(512)
    elapsed = time.perf_counter() - started
    audio_time = loops * 512 / float(engine.sr)
    factor = audio_time / elapsed
    print("realtime x%.2f  (8 voices, filter, reverb)" % factor)
    assert factor > 1.3, factor


def test_ui():
    try:
        from synth.app import DonSynApp
    except Exception as exc:
        print("UI import failed:", exc)
        raise
    app = DonSynApp(audio=False)
    try:
        app.update()
        app._press(60, "test")
        audio = app.engine.render(4096)
        assert _rms(audio) > 0.01
        app.update()
    finally:
        app.destroy()


def main():
    test_quantize()
    test_keys()
    test_envelope()
    test_pitch_and_silence()
    test_poly_sustain_mono()
    test_arp_and_presets()
    test_speed()
    test_ui()
    print("ALL OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
