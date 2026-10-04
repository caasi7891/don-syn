"""Block oscillators, envelopes, filters, and delay lines."""

from __future__ import annotations

import math

import numpy as np

ATTACK, DECAY, SUSTAIN, RELEASE, OFF = 0, 1, 2, 3, 4
SINE, TRI, SAW, SQUARE, PULSE, NOISE = 0, 1, 2, 3, 4, 5
TWO_PI = 2.0 * math.pi


def mtof(note, tune_cents=0.0):
    return 440.0 * (2.0 ** ((float(note) - 69.0 + float(tune_cents) / 100.0) / 12.0))


def polyblep(t, dt):
    dt = np.maximum(dt, 1e-8)
    out = np.zeros_like(t, dtype=np.float64)
    mask = t < dt
    if np.any(mask):
        x = t[mask] / dt[mask]
        out[mask] = 2.0 * x - x * x - 1.0
    mask = t > (1.0 - dt)
    if np.any(mask):
        x = (t[mask] - 1.0) / dt[mask]
        out[mask] = x * x + 2.0 * x + 1.0
    return out


def render_wave(kind, phases, incr, pw):
    kind = int(kind)
    if kind == SINE:
        return np.sin(TWO_PI * phases)
    if kind == TRI:
        return 1.0 - 4.0 * np.abs(phases - 0.5)
    if kind == SAW:
        return (2.0 * phases - 1.0) - polyblep(phases, incr)
    if kind == NOISE:
        return np.random.uniform(-1.0, 1.0, phases.shape[0])
    width = 0.5 if kind == SQUARE else float(pw)
    width = min(0.95, max(0.05, width))
    wave = np.where(phases < width, 1.0, -1.0).astype(np.float64)
    wave += polyblep(phases, incr)
    wave -= polyblep(np.mod(phases - width, 1.0), incr)
    return wave


def advance_phase(phase, incr):
    incr = np.asarray(incr, dtype=np.float64)
    phases = np.mod(phase + np.cumsum(incr) - incr, 1.0)
    new_phase = (float(phase) + float(np.sum(incr))) % 1.0
    return phases, new_phase


def _ramp(level, end, take):
    if take <= 1:
        return np.array([end], dtype=np.float32)
    return np.linspace(level, end, take, dtype=np.float32)


def env_block(level, stage, n, sr, attack, decay, sustain, release):
    out = np.zeros(n, dtype=np.float32)
    pos = 0
    level = float(level)
    stage = int(stage)
    sustain = float(sustain)
    guard = 0
    while pos < n and guard < 8:
        guard += 1
        left = n - pos
        if stage == ATTACK:
            dur = max(1, int(round(max(0.0, attack) * sr)))
            remain = max(1, int(round(dur * max(0.0, 1.0 - level))))
            take = min(left, remain)
            end = level + (1.0 - level) * (take / float(remain))
            out[pos:pos + take] = _ramp(level, end, take)
            level = float(end)
            pos += take
            if take >= remain or level >= 0.999:
                level = 1.0
                stage = DECAY
        elif stage == DECAY:
            if sustain >= 0.999 or level <= sustain + 1e-4:
                level = sustain
                stage = SUSTAIN
                continue
            dur = max(1, int(round(max(0.001, decay) * sr)))
            span = max(1e-4, 1.0 - sustain)
            remain = max(1, int(round(dur * (level - sustain) / span)))
            take = min(left, remain)
            end = level + (sustain - level) * (take / float(remain))
            out[pos:pos + take] = _ramp(level, end, take)
            level = float(end)
            pos += take
            if take >= remain or level <= sustain + 1e-4:
                level = min(level, sustain) if level < sustain else level
                if abs(level - sustain) < 1e-3 or take >= remain:
                    level = sustain
                    stage = SUSTAIN
        elif stage == SUSTAIN:
            out[pos:] = sustain
            level = sustain
            pos = n
        elif stage == RELEASE:
            if level <= 1e-4:
                level = 0.0
                stage = OFF
                pos = n
                continue
            dur = max(1, int(round(max(0.001, release) * sr)))
            remain = max(1, int(round(dur * max(level, 0.0))))
            take = min(left, remain)
            end = level * (1.0 - take / float(remain))
            out[pos:pos + take] = _ramp(level, end, take)
            level = float(end)
            pos += take
            if level <= 1e-4 or take >= remain:
                level = 0.0
                stage = OFF
                pos = n
        else:
            stage = OFF
            level = 0.0
            pos = n
    if pos < n:
        out[pos:] = level
    return out, level, stage


def biquad_coeffs(kind, cutoff, q, sr):
    cutoff = min(max(20.0, float(cutoff)), sr * 0.45)
    q = min(max(0.05, float(q)), 20.0)
    w0 = TWO_PI * cutoff / sr
    cw = math.cos(w0)
    sw = math.sin(w0)
    alpha = sw / (2.0 * q)
    if kind == "hp":
        b0 = (1.0 + cw) * 0.5
        b1 = -(1.0 + cw)
        b2 = (1.0 + cw) * 0.5
    elif kind == "bp":
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
    else:
        b0 = (1.0 - cw) * 0.5
        b1 = 1.0 - cw
        b2 = (1.0 - cw) * 0.5
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def biquad_process(x, z1, z2, b0, b1, b2, a1, a2):
    n = int(x.shape[0])
    y = np.empty(n, dtype=np.float32)
    for i in range(n):
        xi = float(x[i])
        yi = b0 * xi + z1
        z1 = b1 * xi - a1 * yi + z2
        z2 = b2 * xi - a2 * yi
        y[i] = yi
    if n and (not math.isfinite(z1) or not math.isfinite(z2) or not math.isfinite(float(y[-1]))):
        return np.zeros(n, dtype=np.float32), 0.0, 0.0
    if abs(z1) < 1e-20:
        z1 = 0.0
    if abs(z2) < 1e-20:
        z2 = 0.0
    return y, z1, z2


def circ_write(buf, w, data):
    n = int(data.shape[0])
    length = int(buf.shape[0])
    w %= length
    end = w + n
    if end <= length:
        buf[w:end] = data
    else:
        k = length - w
        buf[w:] = data[:k]
        buf[:n - k] = data[k:]


def circ_read(buf, start, n):
    length = int(buf.shape[0])
    start %= length
    end = start + n
    if end <= length:
        return buf[start:end].copy()
    k = length - start
    return np.concatenate((buf[start:], buf[:n - k]))


def circ_read_linear(buf, positions):
    length = int(buf.shape[0])
    pos = np.mod(positions, length)
    i0 = np.floor(pos).astype(np.int32)
    frac = (pos - i0).astype(np.float32)
    i1 = (i0 + 1) % length
    return buf[i0] * (1.0 - frac) + buf[i1] * frac


def delay_feedback(buf, w, x, delay, fb, mode):
    n = int(x.shape[0])
    y = np.empty(n, dtype=np.float32)
    pos = 0
    length = int(buf.shape[0])
    delay = max(1, min(int(delay), length - 1))
    fb = float(fb)
    while pos < n:
        take = min(delay, n - pos)
        delayed = circ_read(buf, w - delay, take)
        src = x[pos:pos + take]
        if mode == "comb":
            y[pos:pos + take] = delayed
            circ_write(buf, w, np.clip(src + delayed * fb, -2.0, 2.0))
        else:
            chunk = -fb * src + delayed
            y[pos:pos + take] = chunk
            circ_write(buf, w, np.clip(src + fb * chunk, -2.0, 2.0))
        w = (w + take) % length
        pos += take
    return y, w


def dc_block(x, x1, y1, r=0.995):
    y = np.empty(x.shape[0], dtype=np.float32)
    for i in range(x.shape[0]):
        xi = float(x[i])
        yi = xi - x1 + r * y1
        x1 = xi
        y1 = yi
        y[i] = yi
    if not math.isfinite(y1):
        return np.zeros_like(y), 0.0, 0.0
    return y, x1, y1
