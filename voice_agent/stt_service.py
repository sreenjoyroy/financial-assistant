from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import speech_recognition as sr
import logging
import os
import uuid
import shutil
from pydub import AudioSegment  # for converting to wav
from datetime import datetime
import json

# ------------------------------
# Setup
# ------------------------------
app = FastAPI(title="Speech-to-Text (STT) Service")

UPLOAD_DIR = "temp_audio"
LOG_FILE = "../logs/stt_logs.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

recognizer = sr.Recognizer()

# ------------------------------
# Transcription Endpoint
# ------------------------------
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.filename.endswith((".wav", ".mp3", ".m4a")):
            raise HTTPException(status_code=400, detail="Only .wav, .mp3, .m4a files are supported.")

        # Save file temporarily
        file_id = str(uuid.uuid4())
        ext = file.filename.rsplit(".", 1)[-1]
        input_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convert to WAV if needed
        if not input_path.endswith(".wav"):
            wav_path = os.path.join(UPLOAD_DIR, f"{file_id}.wav")
            audio = AudioSegment.from_file(input_path)
            audio.export(wav_path, format="wav")
            os.remove(input_path)
            input_path = wav_path

        # Transcribe using speech_recognition
        with sr.AudioFile(input_path) as source:
            audio_data = recognizer.record(source)

        transcription = recognizer.recognize_google(audio_data)

        # Clean up
        os.remove(input_path)

        # Log usage
        logging.info(json.dumps({
            "event": "stt_transcription",
            "filename": file.filename,
            "transcription_id": file_id,
            "timestamp": datetime.utcnow().isoformat(),
            "transcription_chars": len(transcription)
        }))

        return JSONResponse(content={
            "status": "success",
            "transcription_id": file_id,
            "text": transcription
        })

    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Speech was unintelligible.")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Speech recognition error: {e}")
    except Exception as e:
        logging.error(f"STT error: {str(e)}")
        raise HTTPException(status_code=500, detail="Transcription failed.")

# ------------------------------
# Health Check
# ------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok"}
