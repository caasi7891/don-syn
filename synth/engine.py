"""Polyphonic synthesizer engine. The GUI and the audio callback share it."""

from __future__ import annotations

import math
import random
import threading
import time

import numpy as np

from synth.dsp import (
    ATTACK,
    DECAY,
    OFF,
    RELEASE,
    SUSTAIN,
    advance_phase,
    biquad_coeffs,
    biquad_process,
    circ_read_linear,
    circ_write,
    dc_block,
    delay_feedback,
    env_block,
    mtof,
    render_wave,
)
from synth.params import ARP_DIV_BEATS, PARAMS, coerce, defaults, quantize

MAX_VOICES = 16
CHUNK = 128
FILTER_KIND = {0: "lp", 1: "hp", 2: "bp"}
COMBS = (
    (1116, 0.805),
    (1188, 0.827),
    (1277, 0.783),
    (1356, 0.764),
    (1422, 0.796),
    (1491, 0.788),
)
ALLPASS = ((556, 0.7), (441, 0.7))
VOICE_GAIN = 0.3


class Voice:
    __slots__ = (
        "active", "note", "vel", "freq", "phase1", "phase2", "drift",
        "amp_stage", "amp_level", "flt_stage", "flt_level", "z1", "z2", "born",
    )

    def __init__(self):
        self.active = False
        self.note = 60
        self.vel = 0.8
        self.freq = 0.0
        self.phase1 = random.random()
        self.phase2 = random.random()
        self.drift = 0.0
        self.amp_stage = OFF
        self.amp_level = 0.0
        self.flt_stage = OFF
        self.flt_level = 0.0
        self.z1 = 0.0
        self.z2 = 0.0
        self.born = 0

    def kill(self):
        self.active = False
        self.amp_stage = OFF
        self.amp_level = 0.0
        self.flt_stage = OFF
        self.flt_level = 0.0
        self.z1 = 0.0
        self.z2 = 0.0
        self.freq = 0.0

    def release(self):
        if self.active and self.amp_stage < RELEASE:
            self.amp_stage = RELEASE
            self.flt_stage = RELEASE

    def trigger(self, note, vel, born, analog, keep_freq):
        self.note = int(note)
        self.vel = float(vel)
        self.active = True
        target = mtof(self.note)
        if self.freq <= 0.0 or not keep_freq:
            self.freq = target
        self.amp_stage = ATTACK
        self.amp_level = 0.0
        self.flt_stage = ATTACK
        self.flt_level = 0.0
        self.z1 = 0.0
        self.z2 = 0.0
        self.drift = random.uniform(-3.0, 3.0) if analog else 0.0
        self.born = born


class SynthEngine:
    def __init__(self, sr=44100):
        self.sr = int(sr)
        self.p = defaults()
        self.lock = threading.Lock()
        self.voices = [Voice() for _ in range(MAX_VOICES)]
        self.fingers = set()
        self.caught = set()
        self.order = []
        self.vels = {}
        self.sustain = False
        self.analog = True
        self.bend = 0.0
        self.bend_target = 0.0
        self.mod = 0.0
        self.sample_time = 0
        self.lfo_phase = 0.0
        self.sample_hold = 0.0
        self.smooth = {}
        self.scope = np.zeros(2048, dtype=np.float32)
        self.scope_w = 0
        self.peak = 0.0
        self.public_peak = 0.0
        self.public_cpu = 0.0
        self.public_raw = ()
        self.public_notes = ()
        self.public_status = ""
        self.arp_live = False
        self.arp_pos = 0
        self.arp_index = 0
        self.arp_dir = 1
        self.arp_voice = None
        self.arp_current = None
        self.arp_triggers = 0
        self.recording = False
        self.rec_overflow = False
        self._rec = []
        self.rec_samples = 0
        self.dc_x = 0.0
        self.dc_y = 0.0
        self.delay_buf = np.zeros(int(self.sr * 2.0), dtype=np.float32)
        self.delay_w = 0
        self.chorus_buf = np.zeros(int(self.sr * 0.08), dtype=np.float32)
        self.chorus_w = 0
        self.chorus_phase = 0.0
        self.combs = []
        for delay, fb in COMBS:
            samples = max(8, int(delay * self.sr / 44100.0))
            self.combs.append({
                "buf": np.zeros(samples + 8, dtype=np.float32),
                "w": 0,
                "d": samples,
                "fb": fb,
            })
        self.allpasses = []
        for delay, fb in ALLPASS:
            samples = max(8, int(delay * self.sr / 44100.0))
            self.allpasses.append({
                "buf": np.zeros(samples + 8, dtype=np.float32),
                "w": 0,
                "d": samples,
                "fb": fb,
            })
        self._publish()

    def set_param(self, name, value):
        if name not in PARAMS:
            return
        value = coerce(name, value)
        with self.lock:
            self.p[name] = value
            if name == "arp_on":
                self._on_arp_toggled()
            elif name == "hold":
                self._release_caught_if_needed()
                self._after_held_change()
            elif name in ("scale", "root", "voice_mode", "poly") and not int(self.p["arp_on"]):
                self.sync_voices()
                self._publish()

    def load(self, params):
        with self.lock:
            for name in PARAMS:
                if name == "hold":
                    continue
                if name in params:
                    self.p[name] = coerce(name, params[name])
                else:
                    self.p[name] = coerce(name, PARAMS[name].default)
            self._hard_stop()
            self._clear_fx()
            self.arp_live = False
            self.arp_pos = 0
            self.arp_index = 0
            self.arp_dir = 1
            if not int(self.p["arp_on"]):
                self.sync_voices()
            self._publish()

    def params_snapshot(self):
        with self.lock:
            return {name: self.p[name] for name in PARAMS if name != "hold"}

    def set_bend(self, value):
        self.bend_target = max(-1.0, min(1.0, float(value)))

    def set_mod(self, value):
        self.mod = max(0.0, min(1.0, float(value)))

    def set_sustain(self, on):
        with self.lock:
            self.sustain = bool(on)
            self._release_caught_if_needed()
            self._after_held_change()

    def note_down(self, raw, vel=None):
        raw = int(raw)
        with self.lock:
            if raw in self.fingers:
                return
            self.fingers.add(raw)
            if raw in self.order:
                self.order.remove(raw)
            self.order.append(raw)
            if vel is None:
                vel = self.p["velocity"]
            self.vels[raw] = float(vel)
            self.caught.discard(raw)
            self._after_held_change()

    def note_up(self, raw):
        raw = int(raw)
        with self.lock:
            if raw not in self.fingers:
                return
            self.fingers.discard(raw)
            if self._pedal():
                self.caught.add(raw)
            else:
                self._forget(raw)
            self._after_held_change()

    def panic(self):
        with self.lock:
            self.fingers.clear()
            self.caught.clear()
            self.order.clear()
            self.vels.clear()
            self.sustain = False
            self.arp_live = False
            self.arp_pos = 0
            self._hard_stop()
            self._publish()

    def release_all(self):
        with self.lock:
            self.fingers.clear()
            self.caught.clear()
            self.order.clear()
            self.sustain = False
            self.arp_live = False
            for voice in self.voices:
                voice.release()
            self._publish()

    def start_recording(self):
        with self.lock:
            self._rec = []
            self.rec_samples = 0
            self.rec_overflow = False
            self.recording = True

    def stop_recording(self):
        with self.lock:
            self.recording = False
            chunks = self._rec
            self._rec = []
            overflow = self.rec_overflow
        if not chunks:
            return np.zeros(0, dtype=np.float32), overflow
        return np.concatenate(chunks), overflow

    def copy_scope(self):
        if not self.lock.acquire(blocking=False):
            return None
        try:
            return self.scope.copy(), int(self.scope_w)
        finally:
            self.lock.release()

    def render(self, n):
        n = int(n)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        started = time.perf_counter()
        with self.lock:
            audio = self._render_locked(n)
        elapsed = time.perf_counter() - started
        self.public_cpu = elapsed / (n / float(self.sr))
        return audio

    def _pedal(self):
        return bool(self.sustain) or bool(int(self.p["hold"]))

    def _forget(self, raw):
        self.caught.discard(raw)
        if raw in self.order:
            self.order.remove(raw)
        self.vels.pop(raw, None)

    def _release_caught_if_needed(self):
        if self._pedal():
            return
        for raw in list(self.caught):
            if raw not in self.fingers:
                self._forget(raw)

    def _after_held_change(self):
        if int(self.p["arp_on"]):
            self._publish()
            return
        self.sync_voices()
        self._publish()

    def _on_arp_toggled(self):
        self._hard_stop()
        self.arp_live = False
        self.arp_pos = 0
        self.arp_index = 0
        self.arp_dir = 1
        if not int(self.p["arp_on"]):
            self.sync_voices()
        self._publish()

    def _hard_stop(self):
        for voice in self.voices:
            voice.kill()
        self.arp_voice = None

    def _clear_fx(self):
        self.delay_buf.fill(0)
        self.delay_w = 0
        self.chorus_buf.fill(0)
        self.chorus_w = 0
        for line in self.combs + self.allpasses:
            line["buf"].fill(0)
            line["w"] = 0
        self.dc_x = 0.0
        self.dc_y = 0.0

    def _held_raws(self):
        raws = set(self.fingers)
        if self._pedal():
            raws |= self.caught
        return raws

    def _desired(self):
        found = {}
        root = int(self.p["root"])
        scale = int(self.p["scale"])
        for raw in self._held_raws():
            midi = quantize(raw, root, scale)
            vel = self.vels.get(raw, float(self.p["velocity"]))
            if midi in found:
                found[midi] = max(found[midi], vel)
            else:
                found[midi] = vel
        return found

    def _latest(self):
        raws = self._held_raws()
        root = int(self.p["root"])
        scale = int(self.p["scale"])
        for raw in reversed(self.order):
            if raw in raws:
                return quantize(raw, root, scale), self.vels.get(raw, float(self.p["velocity"]))
        return None

    def sync_voices(self):
        if int(self.p["voice_mode"]) == 0:
            self._sync_poly()
        else:
            self._sync_mono(legato=int(self.p["voice_mode"]) == 2)

    def _poly_voices(self):
        count = max(1, min(MAX_VOICES, int(self.p["poly"])))
        return self.voices[:count]

    def _find_held(self, midi, voices):
        for voice in voices:
            if voice.active and voice.note == midi and voice.amp_stage < RELEASE:
                return voice
        return None

    def _alloc_free(self, midi, vel, keep_freq=False):
        voices = self._poly_voices()
        for voice in voices:
            if not voice.active:
                voice.trigger(midi, vel, self.sample_time, self.analog, False)
                return voice
        releasing = [voice for voice in voices if voice.amp_stage >= RELEASE or not voice.active]
        pool = releasing or voices
        voice = min(pool, key=lambda item: (item.amp_level, item.born))
        voice.trigger(midi, vel, self.sample_time, self.analog, keep_freq and voice.freq > 0.0)
        return voice

    def _sync_poly(self):
        desired = self._desired()
        count = max(1, min(MAX_VOICES, int(self.p["poly"])))
        for voice in self.voices[count:]:
            if voice.active and voice.amp_stage < RELEASE:
                voice.release()
        voices = self.voices[:count]
        for voice in voices:
            if voice.active and voice.amp_stage < RELEASE and voice.note not in desired:
                voice.release()
        for midi in sorted(desired, reverse=True):
            existing = self._find_held(midi, voices)
            if existing is not None:
                existing.vel = desired[midi]
                continue
            self._alloc_free(midi, desired[midi])

    def _sync_mono(self, legato):
        for voice in self.voices[1:]:
            if voice.active and voice.amp_stage < RELEASE:
                voice.release()
        voice = self.voices[0]
        latest = self._latest()
        if latest is None:
            if voice.active and voice.amp_stage < RELEASE:
                voice.release()
            return
        midi, vel = latest
        if voice.active and voice.amp_stage < RELEASE and voice.note == midi:
            voice.vel = vel
            return
        if legato and voice.active and voice.amp_stage < RELEASE:
            voice.note = midi
            voice.vel = vel
            return
        keep = float(self.p["glide"]) > 0.001 and voice.freq > 0.0
        voice.trigger(midi, vel, self.sample_time, self.analog, keep)

    def _publish(self):
        raws = set(self.fingers)
        if self._pedal():
            raws |= self.caught
        self.public_raw = tuple(sorted(raws))
        sounding = []
        for voice in self.voices:
            if voice.active and voice.amp_stage < RELEASE:
                sounding.append(voice.note)
        self.public_notes = tuple(sounding)

    def _render_locked(self, n):
        if int(self.p["arp_on"]):
            dry = self._render_arp(n)
        else:
            dry = self._render_voices(n)
        wet = self._effects(dry)
        self._push_scope(wet)
        peak = float(np.max(np.abs(wet))) if n else 0.0
        self.peak = max(self.peak * 0.9, peak)
        self.public_peak = self.peak
        if self.recording:
            self._rec.append(wet.copy())
            self.rec_samples += n
            if self.rec_samples >= self.sr * 600:
                self.recording = False
                self.rec_overflow = True
        self._publish()
        return wet

    def _render_voices(self, n):
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        if n <= CHUNK:
            return self._render_chunk(n)
        parts = []
        left = n
        while left:
            take = CHUNK if left > CHUNK else left
            parts.append(self._render_chunk(take))
            left -= take
        return np.concatenate(parts)

    def _smooth(self, key, target, n, tau):
        current = self.smooth.get(key, target)
        coef = 1.0 - math.exp(-n / (self.sr * tau))
        current = current + (target - current) * coef
        self.smooth[key] = current
        return current

    def _next_lfo(self, n):
        rate = float(self.p["lfo_rate"])
        kind = int(self.p["lfo_wave"])
        incr = rate / float(self.sr)
        if kind == 4:
            out = np.empty(n, dtype=np.float32)
            phase = self.lfo_phase
            hold = self.sample_hold
            for i in range(n):
                phase += incr
                if phase >= 1.0:
                    phase -= 1.0
                    hold = random.uniform(-1.0, 1.0)
                out[i] = hold
            self.lfo_phase = phase % 1.0
            self.sample_hold = hold
            return out
        phase0 = self.lfo_phase
        idx = np.arange(n, dtype=np.float64)
        phases = np.mod(phase0 + incr * idx, 1.0)
        self.lfo_phase = (phase0 + incr * n) % 1.0
        if kind == 0:
            return np.sin(2.0 * math.pi * phases).astype(np.float32)
        if kind == 1:
            return (1.0 - 4.0 * np.abs(phases - 0.5)).astype(np.float32)
        if kind == 2:
            return (2.0 * phases - 1.0).astype(np.float32)
        return np.where(phases < 0.5, 1.0, -1.0).astype(np.float32)

    def _ratio(self, osc, drift):
        octave = int(self.p["osc%d_oct" % osc])
        semi = int(self.p["osc%d_semi" % osc])
        detune = float(self.p["osc%d_detune" % osc])
        return 2.0 ** (octave + semi / 12.0 + (detune + drift) / 1200.0)

    def _render_chunk(self, n):
        mix = np.zeros(n, dtype=np.float32)
        sr = float(self.sr)
        lfo = self._next_lfo(n)
        depth = min(1.0, max(0.0, float(self.p["lfo_depth"]) + self.mod))
        dest = int(self.p["lfo_dest"])
        coef = 1.0 - math.exp(-n / (sr * 0.015))
        self.bend += (self.bend_target - self.bend) * coef
        bend_ratio = 2.0 ** (self.bend * 2.0 / 12.0)
        tune_ratio = 2.0 ** (float(self.p["tune"]) / 1200.0)
        glide = float(self.p["glide"])
        ftype = int(self.p["filter_type"])
        base_cut = self._smooth("cutoff", float(self.p["cutoff"]), n, 0.02)
        res = self._smooth("reso", float(self.p["resonance"]), n, 0.02)
        q = 0.707 + (res ** 1.15) * 14.0
        env_amt = float(self.p["filter_env"])
        track_amt = float(self.p["filter_track"])
        amp_a = float(self.p["amp_a"])
        amp_d = float(self.p["amp_d"])
        amp_s = float(self.p["amp_s"])
        amp_r = float(self.p["amp_r"])
        flt_a = float(self.p["flt_a"])
        flt_d = float(self.p["flt_d"])
        flt_s = float(self.p["flt_s"])
        flt_r = float(self.p["flt_r"])
        wave1 = int(self.p["osc1_wave"])
        wave2 = int(self.p["osc2_wave"])
        level1 = float(self.p["osc1_level"])
        level2 = float(self.p["osc2_level"])
        pw1 = float(self.p["osc1_pw"])
        pw2 = float(self.p["osc2_pw"])
        if dest == 3 and depth > 0.0:
            wobble = float(np.mean(lfo)) * depth * 0.4
            pw1 = min(0.95, max(0.05, pw1 + wobble))
            pw2 = min(0.95, max(0.05, pw2 + wobble))
        lfo_mean = float(np.mean(lfo)) if dest == 1 else 0.0
        for voice in self.voices:
            if not voice.active:
                continue
            amp_env, voice.amp_level, voice.amp_stage = env_block(
                voice.amp_level, voice.amp_stage, n, sr, amp_a, amp_d, amp_s, amp_r
            )
            flt_env, voice.flt_level, voice.flt_stage = env_block(
                voice.flt_level, voice.flt_stage, n, sr, flt_a, flt_d, flt_s, flt_r
            )
            if voice.amp_stage == OFF:
                voice.active = False
                voice.freq = 0.0
                continue
            if float(amp_env.max()) < 1e-6:
                continue
            target = mtof(voice.note)
            if glide < 0.001 or voice.freq <= 0.0:
                freqs = np.full(n, target, dtype=np.float64)
                voice.freq = target
            else:
                tau = max(1.0, glide * sr)
                decay = math.exp(-1.0 / tau)
                steps = np.arange(1, n + 1, dtype=np.float64)
                freqs = target + (voice.freq - target) * np.power(decay, steps)
                voice.freq = float(freqs[-1])
            freqs *= tune_ratio * bend_ratio
            if dest == 0 and depth > 0.0:
                freqs = freqs * np.power(2.0, lfo * (depth * 2.0 / 12.0))
            ratio1 = self._ratio(1, voice.drift)
            ratio2 = self._ratio(2, -voice.drift)
            incr1 = freqs * ratio1 / sr
            incr2 = freqs * ratio2 / sr
            phases1, voice.phase1 = advance_phase(voice.phase1, incr1)
            phases2, voice.phase2 = advance_phase(voice.phase2, incr2)
            osc = render_wave(wave1, phases1, incr1, pw1) * level1
            osc += render_wave(wave2, phases2, incr2, pw2) * level2
            osc = np.clip(osc, -1.5, 1.5).astype(np.float32)
            if ftype < 3:
                cents = (
                    float(np.mean(flt_env)) * env_amt * 6.0
                    + ((voice.note - 60) / 12.0) * track_amt
                    + lfo_mean * depth * 4.0
                )
                cutoff = base_cut * (2.0 ** cents)
                coeffs = biquad_coeffs(FILTER_KIND[ftype], cutoff, q, sr)
                osc, voice.z1, voice.z2 = biquad_process(osc, voice.z1, voice.z2, *coeffs)
                osc = np.clip(osc, -2.0, 2.0)
            shaped = amp_env
            if dest == 2 and depth > 0.0:
                trem = 1.0 - depth * (1.0 - (lfo * 0.5 + 0.5)) * 0.85
                shaped = shaped * trem
            mix += osc * shaped * (voice.vel * VOICE_GAIN)
        self.sample_time += n
        return mix

    def _arp_step(self):
        bpm = max(40.0, float(self.p["arp_bpm"]))
        division = ARP_DIV_BEATS[int(self.p["arp_div"]) % len(ARP_DIV_BEATS)]
        return max(64, int(self.sr * (60.0 / bpm) * division))

    def _arp_notes(self):
        base = sorted(self._desired())
        if not base:
            return []
        octaves = max(1, min(3, int(self.p["arp_oct"])))
        notes = []
        for octave in range(octaves):
            for note in base:
                notes.append(note + 12 * octave)
        return notes

    def _arp_on(self, notes):
        mode = int(self.p["arp_mode"])
        if len(notes) == 1:
            note = notes[0]
        elif mode == 3:
            note = random.choice(notes)
        elif mode == 0:
            note = notes[self.arp_index % len(notes)]
            self.arp_index += 1
        elif mode == 1:
            note = notes[-(self.arp_index % len(notes)) - 1]
            self.arp_index += 1
        else:
            if self.arp_index >= len(notes):
                self.arp_index = len(notes) - 1
                self.arp_dir = -1
            if self.arp_index < 0:
                self.arp_index = 0
                self.arp_dir = 1
            note = notes[self.arp_index]
            nxt = self.arp_index + self.arp_dir
            if nxt >= len(notes) or nxt < 0:
                self.arp_dir *= -1
                nxt = self.arp_index + self.arp_dir
                if nxt >= len(notes) or nxt < 0:
                    nxt = self.arp_index
            self.arp_index = nxt
        self.arp_voice = self._alloc_free(int(note), float(self.p["velocity"]))
        self.arp_live = True
        self.arp_current = int(note)
        self.arp_triggers += 1

    def _arp_off(self):
        self.arp_live = False
        voice = self.arp_voice
        if voice is not None and voice.active and voice.amp_stage < RELEASE and voice.note == self.arp_current:
            voice.release()

    def _render_arp(self, n):
        out = np.zeros(n, dtype=np.float32)
        pos = 0
        guard = 0
        while pos < n and guard < 64:
            guard += 1
            notes = self._arp_notes()
            if not notes:
                if self.arp_live:
                    self._arp_off()
                if pos < n:
                    out[pos:] = self._render_voices(n - pos)
                return out
            step = self._arp_step()
            gate = int(step * float(self.p["arp_gate"]))
            gate = max(32, min(step - 16, gate))
            if self.arp_pos <= 0 and not self.arp_live:
                self._arp_on(notes)
                self.arp_pos = 0
            if self.arp_live and self.arp_pos >= gate:
                self._arp_off()
            boundary = gate if self.arp_live else step
            if boundary <= self.arp_pos:
                self.arp_pos = 0
                continue
            take = min(n - pos, boundary - self.arp_pos)
            if take <= 0:
                self.arp_pos = 0
                continue
            out[pos:pos + take] = self._render_voices(take)
            self.arp_pos += take
            pos += take
            if self.arp_pos >= step:
                self.arp_pos = 0
        return out

    def _effects(self, x):
        x = np.asarray(x, dtype=np.float32)
        drive = self._smooth("drive", float(self.p["drive"]), len(x), 0.03)
        if drive > 1.02:
            gain = 1.0 + (drive - 1.0) * 2.2
            x = np.tanh(x * gain).astype(np.float32)
        mix = self._smooth("chorus", float(self.p["chorus_mix"]), len(x), 0.03)
        x = self._chorus(x, mix)
        mix = self._smooth("delay", float(self.p["delay_mix"]), len(x), 0.03)
        x = self._delay(x, mix, float(self.p["delay_time"]), float(self.p["delay_fb"]))
        mix = self._smooth("reverb", float(self.p["reverb_mix"]), len(x), 0.04)
        x = self._reverb(x, mix)
        volume = self._smooth("vol", float(self.p["volume"]), len(x), 0.02)
        x = np.tanh(x * volume).astype(np.float32)
        x, self.dc_x, self.dc_y = dc_block(x, self.dc_x, self.dc_y)
        return x

    def _chorus(self, x, mix):
        n = len(x)
        buf = self.chorus_buf
        w = self.chorus_w
        circ_write(buf, w, x)
        idx = np.arange(n, dtype=np.float64)
        phase = self.chorus_phase + idx * (0.28 / self.sr)
        if mix >= 0.001:
            lfo1 = np.sin(2.0 * math.pi * phase)
            lfo2 = np.sin(2.0 * math.pi * (phase * 1.31 + 0.4))
            d1 = 0.018 * self.sr + lfo1 * 0.004 * self.sr
            d2 = 0.023 * self.sr + lfo2 * 0.005 * self.sr
            tap1 = circ_read_linear(buf, w + idx - d1)
            tap2 = circ_read_linear(buf, w + idx - d2)
            wet = 0.5 * (tap1 + tap2)
            y = x * (1.0 - mix * 0.75) + wet * mix
        else:
            y = x
        self.chorus_w = (w + n) % len(buf)
        self.chorus_phase = float((phase[-1] + 0.28 / self.sr) % 1.0) if n else self.chorus_phase
        return y.astype(np.float32)

    def _delay(self, x, mix, time_s, fb):
        delay = int(max(1, min(len(self.delay_buf) - 2, time_s * self.sr)))
        wet, self.delay_w = delay_feedback(self.delay_buf, self.delay_w, x, delay, min(0.92, fb), "comb")
        if mix < 0.001:
            return x
        return (x * (1.0 - mix) + wet * mix).astype(np.float32)

    def _reverb(self, x, mix):
        if mix < 0.001:
            return x
        wet = np.zeros_like(x)
        for comb in self.combs:
            delayed, comb["w"] = delay_feedback(
                comb["buf"], comb["w"], x, comb["d"], comb["fb"], "comb"
            )
            wet += delayed
        wet *= 1.0 / len(self.combs)
        for ap in self.allpasses:
            wet, ap["w"] = delay_feedback(ap["buf"], ap["w"], wet, ap["d"], ap["fb"], "allpass")
        return (x * (1.0 - mix) + wet * mix).astype(np.float32)

    def _push_scope(self, out):
        n = len(out)
        buf = self.scope
        length = len(buf)
        if n >= length:
            buf[:] = out[-length:]
            self.scope_w = 0
            return
        w = self.scope_w
        end = w + n
        if end <= length:
            buf[w:end] = out
        else:
            k = length - w
            buf[w:] = out[:k]
            buf[:n - k] = out[k:]
        self.scope_w = (w + n) % length
