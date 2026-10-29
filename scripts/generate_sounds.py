"""Generate multiple notification sound files for different tones.

Tones:
  - calm: two-note ascending (A5→E6), soft decay (already exists as focus_chime)
  - energetic: three-note rising arpeggio (C5→E5→G5), brighter
  - minimal: single short note (E5), very brief
  - gentle: soft bell (G5→B5), slow decay
  - success: major chord (C5+E5+G5), triumphant but short

Output: src/assets/sounds/tone_*.wav
"""
import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "assets" / "sounds"
SAMPLE_RATE = 44100


def _envelope(t, duration, attack=0.01, release=0.3):
    """ADSR-ish envelope: quick attack, exponential release."""
    if t < attack:
        return t / attack
    return math.exp(-(t - attack) * release * 5)


def _write_wav(path, samples, duration):
    """Write samples (list of floats in [-1,1]) to a WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for s in samples:
            s = max(-1.0, min(1.0, s))
            w.writeframes(struct.pack("<h", int(s * 32767)))
    print(f"  {path.name}: {path.stat().st_size} bytes, {duration:.1f}s")


def _generate_tone(path, freqs, duration=0.5, amplitude=0.2, release=0.3):
    """Generate a tone with one or more frequencies."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, duration, release=release)
        wave_sum = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        samples.append(env * amplitude * wave_sum)
    _write_wav(path, samples, duration)


def _generate_arpeggio(path, notes, note_duration=0.15, amplitude=0.2):
    """Generate a rising arpeggio."""
    total_duration = note_duration * len(notes)
    n = int(SAMPLE_RATE * total_duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        note_idx = min(int(t / note_duration), len(notes) - 1)
        local_t = t - note_idx * note_duration
        env = _envelope(local_t, note_duration, release=0.5)
        freq = notes[note_idx]
        samples.append(env * amplitude * math.sin(2 * math.pi * freq * t))
    _write_wav(path, samples, total_duration)


def _generate_chord(path, freqs, duration=0.6, amplitude=0.15):
    """Generate a chord (all notes simultaneously)."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, duration, release=0.2)
        wave_sum = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        samples.append(env * amplitude * wave_sum)
    _write_wav(path, samples, duration)


def main():
    print("Generating notification sounds...")

    # Calm (already exists as focus_chime, regenerate for consistency)
    _generate_tone(OUT / "tone_calm.wav",
                   freqs=[880, 1319], duration=0.6, amplitude=0.2, release=0.3)

    # Energetic: rising C major arpeggio
    _generate_arpeggio(OUT / "tone_energetic.wav",
                       notes=[523, 659, 784], note_duration=0.15, amplitude=0.2)

    # Minimal: single short E5
    _generate_tone(OUT / "tone_minimal.wav",
                   freqs=[659], duration=0.2, amplitude=0.2, release=0.8)

    # Gentle: soft G5→B5 bell
    _generate_tone(OUT / "tone_gentle.wav",
                   freqs=[784, 988], duration=0.8, amplitude=0.15, release=0.2)

    # Success: C major chord
    _generate_chord(OUT / "tone_success.wav",
                    freqs=[523, 659, 784], duration=0.5, amplitude=0.12)

    print("Done!")


if __name__ == "__main__":
    main()
