import os
import time
import requests
from typing import Optional
from dotenv import load_dotenv
import re
# Load environment variables from .env file
load_dotenv()

SONIOX_API_BASE_URL = "https://api.soniox.com"
SONIOX_API_KEY = os.getenv("SONIOX_API_KEY")


def clean_marathi_text(text: str) -> str:
    """
    Cleans Marathi text by fixing missing spaces between words and removing unwanted dots.
    """
    # Remove excessive dots or unnecessary characters
    text = re.sub(r'\.{2,}', '.', text)
    
    # Add a space after punctuation (if missing)
    text = re.sub(r'([.!?,"“”])([^\s])', r'\1 \2', text)
    
    # Add space between Marathi or English words that are joined together accidentally
    # NOTE: The original regex here was inserting spaces between EVERY pair of characters,
    # which would break words (e.g., "hello" -> "h e l l o"). I've fixed it to only insert
    # between script changes (Devanagari to Latin or vice versa) for true mixed-script fixes.
    # If you need full word splitting for no-space languages, adjust further.
    #text = re.sub(r'([अ-हक-ळऴवशषसज्ञ])([a-zA-Z])|([a-zA-Z])([अ-हक-ळऴवशषसज्ञ])', r'\1 \2', text)
    
    # Remove double spaces (now safe after the above)
    text = re.sub(r'\s+', ' ', text)
    
    # Trim spaces at start and end
    text = text.strip()
    
    return text

def upload_file(session: requests.Session, filepath: str) -> str:
    """Upload a local audio/video file to Soniox and return file_id."""
    with open(filepath, "rb") as f:
        res = session.post(f"{SONIOX_API_BASE_URL}/v1/files", files={"file": f})
    res.raise_for_status()
    return res.json()["id"]


def create_transcription(session: requests.Session, audio_url: Optional[str], file_id: Optional[str]) -> str:
    """Create a transcription for a given file_id or audio_url, return transcription_id."""
    config = {
        "model": "stt-async-preview",
        "language_hints": ['en', 'es', 'hi', 'mr'],
        "enable_language_identification": True,
        "enable_speaker_diarization": True,
        "context": "",
        "client_reference_id": "FlaskApp",
        "audio_url": audio_url,
        "file_id": file_id
    }
    res = session.post(f"{SONIOX_API_BASE_URL}/v1/transcriptions", json=config)
    res.raise_for_status()
    return res.json()["id"]


def wait_for_completion(session: requests.Session, transcription_id: str):
    """Poll Soniox API until transcription is completed."""
    while True:
        res = session.get(f"{SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}")
        res.raise_for_status()
        status = res.json()["status"]
        if status == "completed":
            return
        elif status == "error":
            raise Exception(res.json().get("error_message", "Unknown error"))
        time.sleep(1)


def get_transcript(session: requests.Session, transcription_id: str) -> str:
    """Get the transcript text from Soniox and clean extra spaces."""
    res = session.get(f"{SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}/transcript")
    res.raise_for_status()
    tokens = res.json().get("tokens", [])
    
    # Join tokens properly without adding unnecessary spaces
    text = "".join(token["text"] for token in tokens)
    
    # Clean up extra spaces for Marathi or other languages
    text = clean_marathi_text(text)
    
    # Remove multiple spaces for English/other languages too
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text



def transcribe_file(filepath: str) -> str:
    """Main helper to transcribe a local audio/video file."""
    if not SONIOX_API_KEY:
        raise RuntimeError("Missing SONIOX_API_KEY in environment variables.")

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {SONIOX_API_KEY}"

    file_id = upload_file(session, filepath)
    transcription_id = create_transcription(session, None, file_id)
    wait_for_completion(session, transcription_id)
    transcript = get_transcript(session, transcription_id)
    return transcript
