"""Parameter ranges, scale tables, and quantization."""

from __future__ import annotations


class Spec:
    def __init__(self, default, lo, hi, kind):
        self.default = default
        self.lo = lo
        self.hi = hi
        self.kind = kind  # int, lin, log


PARAMS = {
    "osc1_wave": Spec(2, 0, 5, "int"),
    "osc1_oct": Spec(0, -2, 2, "int"),
    "osc1_semi": Spec(0, -12, 12, "int"),
    "osc1_detune": Spec(-8.0, -100.0, 100.0, "lin"),
    "osc1_level": Spec(0.72, 0.0, 1.0, "lin"),
    "osc1_pw": Spec(0.5, 0.05, 0.95, "lin"),
    "osc2_wave": Spec(2, 0, 5, "int"),
    "osc2_oct": Spec(0, -2, 2, "int"),
    "osc2_semi": Spec(0, -12, 12, "int"),
    "osc2_detune": Spec(8.0, -100.0, 100.0, "lin"),
    "osc2_level": Spec(0.42, 0.0, 1.0, "lin"),
    "osc2_pw": Spec(0.5, 0.05, 0.95, "lin"),
    "filter_type": Spec(0, 0, 3, "int"),
    "cutoff": Spec(2400.0, 60.0, 14000.0, "log"),
    "resonance": Spec(0.18, 0.0, 1.0, "lin"),
    "filter_env": Spec(0.32, 0.0, 1.0, "lin"),
    "filter_track": Spec(0.25, 0.0, 1.0, "lin"),
    "amp_a": Spec(0.012, 0.001, 4.0, "log"),
    "amp_d": Spec(0.22, 0.001, 4.0, "log"),
    "amp_s": Spec(0.72, 0.0, 1.0, "lin"),
    "amp_r": Spec(0.35, 0.001, 6.0, "log"),
    "flt_a": Spec(0.01, 0.001, 4.0, "log"),
    "flt_d": Spec(0.22, 0.001, 4.0, "log"),
    "flt_s": Spec(0.35, 0.0, 1.0, "lin"),
    "flt_r": Spec(0.3, 0.001, 6.0, "log"),
    "lfo_wave": Spec(0, 0, 4, "int"),
    "lfo_rate": Spec(5.0, 0.05, 30.0, "log"),
    "lfo_depth": Spec(0.0, 0.0, 1.0, "lin"),
    "lfo_dest": Spec(0, 0, 3, "int"),
    "voice_mode": Spec(0, 0, 2, "int"),
    "glide": Spec(0.0, 0.0, 1.5, "lin"),
    "poly": Spec(8, 1, 16, "int"),
    "scale": Spec(0, 0, 5, "int"),
    "root": Spec(0, 0, 11, "int"),
    "velocity": Spec(0.9, 0.05, 1.0, "lin"),
    "tune": Spec(0.0, -100.0, 100.0, "lin"),
    "arp_on": Spec(0, 0, 1, "int"),
    "arp_mode": Spec(0, 0, 3, "int"),
    "arp_bpm": Spec(120, 40, 240, "int"),
    "arp_div": Spec(2, 0, 4, "int"),
    "arp_oct": Spec(1, 1, 3, "int"),
    "arp_gate": Spec(0.5, 0.1, 0.95, "lin"),
    "drive": Spec(1.0, 1.0, 24.0, "lin"),
    "delay_mix": Spec(0.0, 0.0, 1.0, "lin"),
    "delay_time": Spec(0.3, 0.05, 1.2, "log"),
    "delay_fb": Spec(0.35, 0.0, 0.9, "lin"),
    "chorus_mix": Spec(0.0, 0.0, 1.0, "lin"),
    "reverb_mix": Spec(0.14, 0.0, 1.0, "lin"),
    "volume": Spec(0.8, 0.0, 1.0, "lin"),
    "hold": Spec(0, 0, 1, "int"),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALE_NOTES = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    [0, 2, 4, 5, 7, 9, 11],
    [0, 2, 3, 5, 7, 8, 10],
    [0, 2, 4, 7, 9],
    [0, 3, 5, 6, 7, 10],
    [0, 2, 3, 5, 7, 9, 10],
]

ARP_DIV_BEATS = [1.0, 0.5, 0.25, 1.0 / 3.0, 0.75]


def defaults():
    data = {}
    for name, spec in PARAMS.items():
        data[name] = coerce(name, spec.default)
    return data


def coerce(name, value):
    spec = PARAMS[name]
    if spec.kind == "int":
        value = int(round(float(value)))
    else:
        value = float(value)
    if value < spec.lo:
        value = spec.lo
    elif value > spec.hi:
        value = spec.hi
    if spec.kind == "int":
        return int(value)
    return float(value)


def quantize(note, root, scale_id):
    scale = SCALE_NOTES[int(scale_id) % len(SCALE_NOTES)]
    note = int(note)
    if len(scale) == 12:
        return note
    pc = (note - int(root)) % 12
    best = 0
    best_abs = 99
    for degree in scale:
        delta = (degree - pc + 6) % 12 - 6
        if abs(delta) < best_abs:
            best_abs = abs(delta)
            best = delta
    return note + best


def midi_name(midi):
    midi = int(midi)
    return "%s%d" % (NOTE_NAMES[midi % 12], (midi // 12) - 1)
