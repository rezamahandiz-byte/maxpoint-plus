"""Generate a calm focus chime — a two-note ascending tone with soft decay.

Output: src/assets/sounds/maxpoint_chime.wav (the resource used by Android notifications)
Format: 16-bit PCM WAV, mono, 44100 Hz, ~0.6 seconds.

The chime is intentionally quiet (peak amplitude 0.25) and short so it
doesn't startle — it asks for attention without demanding it.
"""
import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "assets" / "sounds" / "maxpoint_chime.wav"

SAMPLE_RATE = 44100
DURATION = 0.6  # seconds

# Two notes: A5 (880 Hz) then E6 (1319 Hz) — a calm ascending fifth.
FREQ_1 = 880.0    # A5
FREQ_2 = 1319.0   # E6
SWITCH_AT = 0.25  # second note starts here


def _sample(t: float) -> float:
    """Compute one sample at time t (seconds)."""
    if t < SWITCH_AT:
        freq = FREQ_1
        local_t = t
    else:
        freq = FREQ_2
        local_t = t - SWITCH_AT
    # Exponential decay envelope — soft attack, gentle fade.
    env = math.exp(-local_t * 3.5)
    # Slight vibrato for warmth.
    vibrato = 1.0 + 0.003 * math.sin(2 * math.pi * 6.0 * t)
    return env * 0.25 * math.sin(2 * math.pi * freq * vibrato * t)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(SAMPLE_RATE * DURATION)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(SAMPLE_RATE)
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            s = _sample(t)
            # Clamp to [-1, 1] and convert to signed 16-bit.
            s = max(-1.0, min(1.0, s))
            w.writeframes(struct.pack("<h", int(s * 32767)))
    print(f"chime written: {OUT}  ({OUT.stat().st_size} bytes, {DURATION}s)")


if __name__ == "__main__":
    main()
