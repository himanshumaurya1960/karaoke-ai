from pathlib import Path
import subprocess


# ==========================================
# KARAOKE AI - INTERACTIVE AUDIO MIXER
# ==========================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

STEMS_DIR = PROJECT_DIR / "stems" / "htdemucs" / "test"
OUTPUT_DIR = PROJECT_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)


# ==========================================
# Get volume from user
# ==========================================

def get_volume(name, default=100):

    while True:

        value = input(
            f"{name} volume (0-200%) [{default}%]: "
        ).strip()

        if value == "":
            return default / 100

        try:

            value = float(value)

            if 0 <= value <= 200:
                return value / 100

            print("Please enter a value between 0 and 200.")

        except ValueError:

            print("Please enter a valid number.")


# ==========================================
# Ask for stem volumes
# ==========================================

print()
print("=" * 50)
print("KARAOKE AI - AUDIO MIXER")
print("=" * 50)
print()

print("Set the volume for each stem.")
print("0%   = muted")
print("100% = original volume")
print("200% = double volume")
print()


vocals_volume = get_volume("🎤 Vocals", 0)

drums_volume = get_volume("🥁 Drums", 100)

bass_volume = get_volume("🎸 Bass", 100)

other_volume = get_volume("🎹 Other/Music", 100)


# ==========================================
# Stem files
# ==========================================

vocals = STEMS_DIR / "vocals.wav"
drums = STEMS_DIR / "drums.wav"
bass = STEMS_DIR / "bass.wav"
other = STEMS_DIR / "other.wav"


# ==========================================
# Check files
# ==========================================

for file in [vocals, drums, bass, other]:

    if not file.exists():

        raise FileNotFoundError(
            f"Missing stem file: {file}"
        )


# ==========================================
# Output
# ==========================================

output_file = OUTPUT_DIR / "custom_mix.mp3"


# ==========================================
# FFmpeg filter
# ==========================================

filter_complex = (

    f"[0:a]volume={vocals_volume}[v];"

    f"[1:a]volume={drums_volume}[d];"

    f"[2:a]volume={bass_volume}[b];"

    f"[3:a]volume={other_volume}[o];"

    f"[v][d][b][o]"
    f"amix=inputs=4:"
    f"duration=longest:"
    f"dropout_transition=2"
    f"[mix]"
)


# ==========================================
# FFmpeg command
# ==========================================

command = [

    "ffmpeg",

    "-y",

    "-i", str(vocals),

    "-i", str(drums),

    "-i", str(bass),

    "-i", str(other),

    "-filter_complex",
    filter_complex,

    "-map",
    "[mix]",

    "-codec:a",
    "libmp3lame",

    "-b:a",
    "320k",

    str(output_file)
]


# ==========================================
# Display settings
# ==========================================

print()
print("=" * 50)
print("MIX SETTINGS")
print("=" * 50)

print(
    f"🎤 Vocals      : "
    f"{vocals_volume * 100:.0f}%"
)

print(
    f"🥁 Drums       : "
    f"{drums_volume * 100:.0f}%"
)

print(
    f"🎸 Bass        : "
    f"{bass_volume * 100:.0f}%"
)

print(
    f"🎹 Other/Music : "
    f"{other_volume * 100:.0f}%"
)

print()
print("Creating custom mix...")
print()


# ==========================================
# Run FFmpeg
# ==========================================

subprocess.run(command, check=True)


# ==========================================
# Finished
# ==========================================

print()
print("=" * 50)
print("MIX COMPLETED SUCCESSFULLY")
print("=" * 50)

print(f"Output file:")
print(output_file)