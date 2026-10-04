"""Computer-keyboard piano map.

Lower row starts at Z = C, upper row at Q = the next C.
Black keys sit on S D G H J and on 2 3 5 6 7 9 0.
"""

CODE_TO_SEMI = {
    90: 0,   # Z
    83: 1,   # S
    88: 2,   # X
    68: 3,   # D
    67: 4,   # C
    86: 5,   # V
    71: 6,   # G
    66: 7,   # B
    72: 8,   # H
    78: 9,   # N
    74: 10,  # J
    77: 11,  # M
    188: 12,  # comma, same C as Q
    76: 13,   # L
    190: 14,  # period
    186: 15,  # semicolon
    191: 16,  # slash
    81: 12,   # Q
    50: 13,   # 2
    87: 14,   # W
    51: 15,   # 3
    69: 16,   # E
    82: 17,   # R
    53: 18,   # 5
    84: 19,   # T
    54: 20,   # 6
    89: 21,   # Y
    55: 22,   # 7
    85: 23,   # U
    73: 24,   # I
    57: 25,   # 9
    79: 26,   # O
    48: 27,   # 0
    80: 28,   # P
}

KEYSYM_TO_SEMI = {
    "z": 0, "s": 1, "x": 2, "d": 3, "c": 4, "v": 5, "g": 6, "b": 7,
    "h": 8, "n": 9, "j": 10, "m": 11, "comma": 12, "l": 13, "period": 14,
    "semicolon": 15, "slash": 16, "q": 12, "2": 13, "w": 14, "3": 15,
    "e": 16, "r": 17, "5": 18, "t": 19, "6": 20, "y": 21, "7": 22, "u": 23,
    "i": 24, "9": 25, "o": 26, "0": 27, "p": 28,
}

LABELS = {
    0: "Z", 1: "S", 2: "X", 3: "D", 4: "C", 5: "V", 6: "G", 7: "B",
    8: "H", 9: "N", 10: "J", 11: "M", 12: "Q", 13: "2", 14: "W", 15: "3",
    16: "E", 17: "R", 18: "5", 19: "T", 20: "6", 21: "Y", 22: "7", 23: "U",
    24: "I", 25: "9", 26: "O", 27: "0", 28: "P",
}

SEMI_COUNT = 29
BLACK = (1, 3, 6, 8, 10)


def is_black(semi):
    return (int(semi) % 12) in BLACK


def semi_from_event(keycode, keysym):
    if keycode in CODE_TO_SEMI:
        return CODE_TO_SEMI[keycode]
    if keysym:
        return KEYSYM_TO_SEMI.get(keysym.lower())
    return None
