"""Factory presets and the user-preset file."""

from __future__ import annotations

import json

from synth.params import PARAMS
from synth.paths import USER_PRESETS


def _pack(**kw):
    data = {}
    for name, spec in PARAMS.items():
        if name == "hold":
            continue
        data[name] = spec.default
    data.update(kw)
    return data


FACTORY_PRESETS = [
    ("기본", _pack()),
    ("클래식 건반", _pack(
        osc1_wave=0, osc1_level=0.8, osc1_detune=-3,
        osc2_wave=1, osc2_oct=1, osc2_level=0.22, osc2_detune=4,
        cutoff=5200, resonance=0.08, filter_env=0.18, filter_track=0.35,
        amp_a=0.004, amp_d=0.38, amp_s=0.42, amp_r=0.5,
        flt_a=0.004, flt_d=0.3, flt_s=0.25, flt_r=0.4,
        reverb_mix=0.24, chorus_mix=0.06, volume=0.85,
    )),
    ("웜 패드", _pack(
        osc1_wave=2, osc1_detune=-14, osc1_level=0.58,
        osc2_wave=2, osc2_detune=14, osc2_level=0.55,
        cutoff=880, resonance=0.2, filter_env=0.28, filter_track=0.2,
        amp_a=0.55, amp_d=0.45, amp_s=0.86, amp_r=1.35,
        flt_a=0.4, flt_d=0.5, flt_s=0.55, flt_r=1.1,
        lfo_wave=0, lfo_rate=0.18, lfo_depth=0.12, lfo_dest=1,
        chorus_mix=0.48, reverb_mix=0.42, volume=0.7,
    )),
    ("슈퍼소 베이스", _pack(
        voice_mode=1, glide=0.05, poly=1,
        osc1_wave=2, osc1_oct=-1, osc1_level=0.85, osc1_detune=-6,
        osc2_wave=3, osc2_oct=-1, osc2_level=0.48, osc2_detune=10,
        cutoff=260, resonance=0.5, filter_env=0.75, filter_track=0.15,
        amp_a=0.004, amp_d=0.16, amp_s=0.58, amp_r=0.12,
        flt_a=0.004, flt_d=0.14, flt_s=0.12, flt_r=0.1,
        drive=3.2, reverb_mix=0.06, volume=0.78,
    )),
    ("플럭", _pack(
        osc1_wave=3, osc1_level=0.75, osc1_pw=0.4,
        osc2_wave=0, osc2_level=0.16, osc2_oct=1,
        cutoff=2600, resonance=0.38, filter_env=0.82,
        amp_a=0.001, amp_d=0.16, amp_s=0.0, amp_r=0.12,
        flt_a=0.001, flt_d=0.13, flt_s=0.0, flt_r=0.1,
        delay_mix=0.22, delay_time=0.22, delay_fb=0.32,
        reverb_mix=0.12, volume=0.82,
    )),
    ("벨", _pack(
        osc1_wave=0, osc1_level=0.7,
        osc2_wave=0, osc2_oct=1, osc2_semi=7, osc2_level=0.28, osc2_detune=5,
        filter_type=3, cutoff=9000,
        amp_a=0.002, amp_d=0.85, amp_s=0.0, amp_r=1.15,
        delay_mix=0.3, delay_time=0.34, delay_fb=0.42,
        reverb_mix=0.28, volume=0.8,
    )),
    ("신스 리드", _pack(
        voice_mode=2, glide=0.09,
        osc1_wave=2, osc1_level=0.7, osc1_detune=-5,
        osc2_wave=2, osc2_level=0.45, osc2_detune=9,
        cutoff=1900, resonance=0.45, filter_env=0.55, filter_track=0.4,
        amp_a=0.02, amp_d=0.14, amp_s=0.72, amp_r=0.18,
        flt_a=0.01, flt_d=0.18, flt_s=0.4, flt_r=0.16,
        lfo_wave=0, lfo_rate=5.5, lfo_depth=0.14, lfo_dest=0,
        drive=2.0, delay_mix=0.24, delay_time=0.25, delay_fb=0.36,
        reverb_mix=0.12, volume=0.75,
    )),
    ("스트링", _pack(
        osc1_wave=2, osc1_detune=-9, osc1_level=0.55,
        osc2_wave=2, osc2_detune=9, osc2_level=0.55,
        cutoff=2700, resonance=0.12, filter_env=0.2, filter_track=0.45,
        amp_a=0.28, amp_d=0.32, amp_s=0.9, amp_r=0.75,
        flt_a=0.22, flt_d=0.3, flt_s=0.6, flt_r=0.6,
        chorus_mix=0.52, reverb_mix=0.34, volume=0.72,
    )),
    ("일렉 피아노", _pack(
        osc1_wave=0, osc1_level=0.85,
        osc2_wave=1, osc2_semi=12, osc2_level=0.22, osc2_detune=3,
        cutoff=4300, resonance=0.16, filter_env=0.4,
        amp_a=0.002, amp_d=0.32, amp_s=0.18, amp_r=0.3,
        flt_a=0.002, flt_d=0.22, flt_s=0.1, flt_r=0.25,
        reverb_mix=0.2, volume=0.84,
    )),
    ("브라스", _pack(
        osc1_wave=2, osc1_level=0.7, osc1_detune=-4,
        osc2_wave=2, osc2_level=0.38, osc2_detune=7,
        cutoff=1050, resonance=0.4, filter_env=0.64, filter_track=0.35,
        amp_a=0.06, amp_d=0.18, amp_s=0.76, amp_r=0.18,
        flt_a=0.07, flt_d=0.2, flt_s=0.42, flt_r=0.16,
        drive=1.7, reverb_mix=0.12, volume=0.76,
    )),
    ("드림 아르프", _pack(
        arp_on=1, arp_mode=2, arp_bpm=108, arp_div=2, arp_oct=2, arp_gate=0.42,
        scale=3, root=0,
        osc1_wave=0, osc1_level=0.7,
        osc2_wave=2, osc2_level=0.22, osc2_detune=6,
        cutoff=3400, resonance=0.22, filter_env=0.48,
        amp_a=0.004, amp_d=0.15, amp_s=0.12, amp_r=0.28,
        flt_a=0.004, flt_d=0.12, flt_s=0.15, flt_r=0.2,
        delay_mix=0.32, delay_time=0.28, delay_fb=0.42,
        reverb_mix=0.36, volume=0.75,
    )),
    ("칩튠", _pack(
        osc1_wave=3, osc1_level=0.7, osc1_pw=0.5,
        osc2_wave=4, osc2_level=0.28, osc2_pw=0.25, osc2_oct=-1,
        lfo_wave=3, lfo_rate=7.5, lfo_depth=0.4, lfo_dest=3,
        filter_type=0, cutoff=4800, resonance=0.08, filter_env=0.1,
        amp_a=0.001, amp_d=0.1, amp_s=0.7, amp_r=0.08,
        drive=1.35, reverb_mix=0.08, volume=0.72,
    )),
]

FACTORY_NAMES = [name for name, _preset in FACTORY_PRESETS]
FACTORY_BY_NAME = {name: preset for name, preset in FACTORY_PRESETS}


def load_user_presets():
    if not USER_PRESETS.exists():
        return {}
    try:
        data = json.loads(USER_PRESETS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    clean = {}
    for name, params in data.items():
        if isinstance(name, str) and isinstance(params, dict):
            clean[name] = params
    return clean


def save_user_presets(presets):
    USER_PRESETS.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
