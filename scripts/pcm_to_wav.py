#!/usr/bin/env python3
"""Convert raw PCM (16-bit signed LE, 16kHz mono) to a playable WAV file.

Usage:
    python scripts/pcm_to_wav.py [path/to/audio.pcm] [output.wav]

Defaults to the most recent session's audio.pcm if no path is given.
"""

import struct
import sys
from pathlib import Path

SAMPLE_RATE = 16000
NUM_CHANNELS = 1
BITS_PER_SAMPLE = 16


def pcm_to_wav(pcm_path: Path, wav_path: Path) -> None:
    pcm_data = pcm_path.read_bytes()
    data_size = len(pcm_data)
    byte_rate = SAMPLE_RATE * NUM_CHANNELS * BITS_PER_SAMPLE // 8
    block_align = NUM_CHANNELS * BITS_PER_SAMPLE // 8

    with open(wav_path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))   # PCM format
        f.write(struct.pack("<H", NUM_CHANNELS))
        f.write(struct.pack("<I", SAMPLE_RATE))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", BITS_PER_SAMPLE))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm_data)

    duration = data_size / byte_rate
    print(f"Wrote {wav_path} ({duration:.1f}s, {data_size} bytes)")


def main() -> None:
    if len(sys.argv) >= 2:
        pcm_path = Path(sys.argv[1])
    else:
        # Find most recent session
        sessions_dir = Path(__file__).parent.parent / "sessions" / "recent"
        sessions = sorted(sessions_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            print("No sessions found in sessions/recent/")
            sys.exit(1)
        pcm_path = sessions[0] / "audio.pcm"
        print(f"Using most recent session: {sessions[0].name}")

    if not pcm_path.exists():
        print(f"File not found: {pcm_path}")
        sys.exit(1)

    wav_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else pcm_path.with_suffix(".wav")
    pcm_to_wav(pcm_path, wav_path)


if __name__ == "__main__":
    main()
