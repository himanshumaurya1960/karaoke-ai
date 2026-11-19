from pathlib import Path
import subprocess

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ==========================================
# PATHS
# ==========================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = PROJECT_DIR / "input"

STEMS_DIR = PROJECT_DIR / "stems"

OUTPUT_DIR = PROJECT_DIR / "output"


INPUT_DIR.mkdir(exist_ok=True)
STEMS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ==========================================
# FASTAPI
# ==========================================

app = FastAPI(
    title="Karaoke AI",
    description="AI-powered music stem separation and audio mixing API",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ALLOWED FORMATS
# ==========================================

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".ogg"
}


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():

    return {
        "message": "Karaoke AI API is running!",
        "status": "success"
    }


# ==========================================
# HEALTH
# ==========================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ==========================================
# UPLOAD
# ==========================================

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No filename provided."
        )


    extension = Path(file.filename).suffix.lower()


    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio format. "
                "Allowed formats: MP3, WAV, M4A, FLAC, OGG."
            )
        )


    filename = Path(file.filename).name

    output_path = INPUT_DIR / filename


    try:

        with output_path.open("wb") as buffer:

            while True:

                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                buffer.write(chunk)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not save file: {error}"
        )


    return {

        "message": "Audio uploaded successfully.",

        "filename": filename,

        "path": str(output_path),

        "size_bytes": output_path.stat().st_size

    }


# ==========================================
# SEPARATE AUDIO
# ==========================================

@app.post("/separate")
def separate_audio(filename: str):

    # --------------------------------------
    # Locate input file
    # --------------------------------------

    input_file = INPUT_DIR / Path(filename).name

    if not input_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found."
        )

    # --------------------------------------
    # Run Demucs AI separation
    # --------------------------------------

    command = [
        str(Path(__import__("sys").executable)),
        "-m",
        "demucs.separate",
        "--device",
        "cuda",
        "--out",
        str(STEMS_DIR),
        str(input_file)
    ]

    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

    except subprocess.CalledProcessError as error:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Audio separation failed.",
                "error": error.stderr
            }
        )

    # --------------------------------------
    # Locate generated stems
    # --------------------------------------

    song_name = input_file.stem

    stem_directory = (
        STEMS_DIR /
        "htdemucs" /
        song_name
    )

    vocals_file = stem_directory / "vocals.wav"
    drums_file = stem_directory / "drums.wav"
    bass_file = stem_directory / "bass.wav"
    other_file = stem_directory / "other.wav"

    # --------------------------------------
    # Check stems
    # --------------------------------------

    for stem_file in [
        vocals_file,
        drums_file,
        bass_file,
        other_file
    ]:

        if not stem_file.exists():

            raise HTTPException(
                status_code=500,
                detail=f"Missing generated stem: {stem_file.name}"
            )

    # --------------------------------------
    # Return result
    # --------------------------------------

    return {
    "message": "Audio separated successfully.",
    "filename": input_file.name,
    "stems": {
    "vocals": f"/stems/{song_name}/vocals",
    "drums": f"/stems/{song_name}/drums",
    "bass": f"/stems/{song_name}/bass",
    "other": f"/stems/{song_name}/other"
}
    
}
# ==========================================
# MIX AUDIO STEMS
# ==========================================

@app.post("/mix")
def mix_audio(
    filename: str,
    vocals: float = 0,
    drums: float = 100,
    bass: float = 100,
    other: float = 100
):

    # --------------------------------------
    # Validate volume values
    # --------------------------------------

    volumes = {
        "vocals": vocals,
        "drums": drums,
        "bass": bass,
        "other": other
    }

    for name, value in volumes.items():

        if value < 0 or value > 200:

            raise HTTPException(
                status_code=400,
                detail=f"{name} volume must be between 0 and 200."
            )


    # --------------------------------------
    # Find separated stems
    # --------------------------------------

    song_name = Path(filename).stem

    stem_directory = (
        STEMS_DIR
        / "htdemucs"
        / song_name
    )


    if not stem_directory.exists():

        raise HTTPException(
            status_code=404,
            detail="Separated stems not found. Run /separate first."
        )


    # --------------------------------------
    # Stem paths
    # --------------------------------------

    vocals_file = stem_directory / "vocals.wav"

    drums_file = stem_directory / "drums.wav"

    bass_file = stem_directory / "bass.wav"

    other_file = stem_directory / "other.wav"


    # --------------------------------------
    # Check stems
    # --------------------------------------

    for stem_file in [
        vocals_file,
        drums_file,
        bass_file,
        other_file
    ]:

        if not stem_file.exists():

            raise HTTPException(
                status_code=404,
                detail=f"Missing stem: {stem_file.name}"
            )


    # --------------------------------------
    # Output
    # --------------------------------------

    output_file = (
        OUTPUT_DIR
        / f"{song_name}_custom_mix.mp3"
    )


    # --------------------------------------
    # Convert percentages to gain
    # --------------------------------------

    vocals_gain = vocals / 100

    drums_gain = drums / 100

    bass_gain = bass / 100

    other_gain = other / 100


    # --------------------------------------
    # FFmpeg filter
    # --------------------------------------

    filter_complex = (

        f"[0:a]volume={vocals_gain}[v];"

        f"[1:a]volume={drums_gain}[d];"

        f"[2:a]volume={bass_gain}[b];"

        f"[3:a]volume={other_gain}[o];"

        f"[v][d][b][o]"
        f"amix="
        f"inputs=4:"
        f"duration=longest:"
        f"dropout_transition=2"
        f"[mix]"
    )


    # --------------------------------------
    # FFmpeg command
    # --------------------------------------

    command = [

        "ffmpeg",

        "-y",

        "-i", str(vocals_file),

        "-i", str(drums_file),

        "-i", str(bass_file),

        "-i", str(other_file),

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


    # --------------------------------------
    # Run FFmpeg
    # --------------------------------------

    try:

        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

    except subprocess.CalledProcessError as error:

        raise HTTPException(

            status_code=500,

            detail={
                "message": "Audio mixing failed.",
                "error": error.stderr
            }

        )


    # --------------------------------------
    # Return result
    # --------------------------------------

    return {

        "message": "Audio mixed successfully.",

        "filename": output_file.name,

        "settings": {

            "vocals": vocals,

            "drums": drums,

            "bass": bass,

            "other": other

        },

        "download_path": str(output_file)

    }

    # --------------------------------------
    # Demucs command
    # --------------------------------------

    command = [

        str(Path(__import__("sys").executable)),

        "-m",
        "demucs.separate",

        "--device",
        "cuda",

        "--out",
        str(STEMS_DIR),

        str(input_file)

    ]


    # --------------------------------------
    # Run Demucs
    # --------------------------------------

    try:

        result = subprocess.run(

            command,

            capture_output=True,

            text=True,

            check=True

        )

    except subprocess.CalledProcessError as error:

        raise HTTPException(

            status_code=500,

            detail={
                "message": "Audio separation failed.",
                "error": error.stderr
            }

        )


    # --------------------------------------
    # Find result folder
    # --------------------------------------

    result_name = input_file.stem

    result_directory = (
        STEMS_DIR
        / "htdemucs"
        / result_name
    )


    # --------------------------------------
    # Check separated stems
    # --------------------------------------

    required_stems = [

        "vocals.wav",
        "drums.wav",
        "bass.wav",
        "other.wav"

    ]


    missing_stems = [

        stem
        for stem in required_stems
        if not (result_directory / stem).exists()

    ]


    if missing_stems:

        raise HTTPException(

            status_code=500,

            detail={
                "message": "Separation completed but stems are missing.",
                "missing": missing_stems
            }

        )


    # --------------------------------------
    # Return result
    # --------------------------------------

    return {

        "message": "Audio separated successfully.",

        "filename": filename,

        "stems": {

            "vocals": str(
                result_directory / "vocals.wav"
            ),

            "drums": str(
                result_directory / "drums.wav"
            ),

            "bass": str(
                result_directory / "bass.wav"
            ),

            "other": str(
                result_directory / "other.wav"
            )

        }

    }
    # ==========================================
# DOWNLOAD MIXED AUDIO
# ==========================================

@app.get("/download/{filename}")
def download_audio(filename: str):

    # --------------------------------------
    # Prevent path traversal
    # --------------------------------------

    safe_filename = Path(filename).name

    file_path = OUTPUT_DIR / safe_filename

    # --------------------------------------
    # Check file
    # --------------------------------------

    if not file_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Audio file not found."
        )

    # --------------------------------------
    # Return file
    # --------------------------------------

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=safe_filename
    )
# ==========================================
# SERVE SEPARATED STEM
# ==========================================

@app.get("/stems/{song_name}/{stem_name}")
def get_stem(song_name: str, stem_name: str):

    allowed_stems = {
        "vocals": "vocals.wav",
        "drums": "drums.wav",
        "bass": "bass.wav",
        "other": "other.wav"
    }

    if stem_name not in allowed_stems:
        raise HTTPException(
            status_code=404,
            detail="Invalid stem name."
        )

    safe_song_name = Path(song_name).stem

    stem_file = (
        STEMS_DIR
        / "htdemucs"
        / safe_song_name
        / allowed_stems[stem_name]
    )

    if not stem_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Stem file not found."
        )

    return FileResponse(
        path=stem_file,
        media_type="audio/wav"
    )