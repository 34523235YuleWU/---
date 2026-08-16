from __future__ import annotations

import math
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sounds"


def write_discard_sound() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    duration = 0.16
    frames: list[int] = []

    for index in range(int(sample_rate * duration)):
        t = index / sample_rate
        envelope = max(0.0, 1.0 - t / duration) ** 2.4
        click = math.sin(2 * math.pi * 1650 * t) * envelope
        wood = math.sin(2 * math.pi * 420 * t) * envelope * 0.45
        value = int((click + wood) * 13000)
        frames.append(max(-32768, min(32767, value)))

    with wave.open(str(OUT / "discard.wav"), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(sample_rate)
        sound.writeframes(b"".join(value.to_bytes(2, "little", signed=True) for value in frames))


if __name__ == "__main__":
    write_discard_sound()
