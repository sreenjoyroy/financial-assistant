from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uuid
import os
import logging
import asyncio
import edge_tts
from datetime import datetime
import json
from fastapi.responses import StreamingResponse
import traceback # Import traceback for detailed error logging

# FastAPI app
app = FastAPI(title="TTS Service (edge-tts)")

# Directory setup
AUDIO_OUTPUT_DIR = "temp_audio"
LOG_FILE = "../logs/tts_logs.json"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Logging setup
# Ensure the logger is configured to output to console as well for immediate debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Add StreamHandler to see logs in console
    ]
)

# Request model
class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-AriaNeural"  # default voice

# POST /speak
@app.post("/speak")
async def speak_text(data: TTSRequest):
    try:
        text = data.text.strip()
        
        logging.info(f"Received TTS request for text (first 100 chars): '{text[:100]}...' with voice: '{data.voice}'")

        if not text:
            logging.warning("Received empty text input for TTS.")
            raise HTTPException(status_code=400, detail="Text input cannot be empty.")

        file_id = str(uuid.uuid4())
        filename = f"{file_id}.mp3"
        output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)

        # Initialize byte counter to check if any data was written
        bytes_written = 0

        try:
            communicate = edge_tts.Communicate(text, voice=data.voice)

            # Generate MP3 file
            logging.info(f"Attempting to write audio to: {output_path}")
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                        bytes_written += len(chunk["data"])
                    elif chunk["type"] == "No-Audio-Received":
                        logging.error(f"Edge TTS returned 'No-Audio-Received' for text: '{text[:50]}...' Voice: {data.voice}")
                        # This chunk type indicates a specific failure from the TTS service
                        raise ValueError("Edge TTS service did not return audio data.")
                    else:
                        logging.debug(f"Received non-audio chunk type: {chunk['type']}")
            
            if bytes_written == 0:
                logging.error(f"No audio data was written to file: {output_path}. Text length: {len(text)}. Voice: {data.voice}")
                raise RuntimeError("TTS generation completed but no audio data was produced.")

            logging.info(f"Successfully wrote {bytes_written} bytes to {output_path}")

        except FileNotFoundError:
            logging.error(f"File system error: Output directory '{AUDIO_OUTPUT_DIR}' or path '{output_path}' not found or accessible.", exc_info=True)
            raise HTTPException(status_code=500, detail="Server file system error during audio generation.")
        except PermissionError:
            logging.error(f"Permission denied: Cannot write to '{output_path}'. Check directory permissions.", exc_info=True)
            raise HTTPException(status_code=500, detail="Server permission error during audio generation.")
        except Exception as e:
            # Catch specific edge_tts related errors here if possible, or general for now
            logging.error(f"Error during edge_tts communication or file writing: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"TTS audio generation failed: {str(e)}")


        # Log event
        logging.info(json.dumps({
            "event": "tts_generation",
            "timestamp": datetime.utcnow().isoformat(),
            "input_chars": len(text),
            "voice": data.voice,
            "output_file": output_path,
            "bytes_generated": bytes_written
        }))

        def iter_audio():
            with open(output_path, "rb") as f:
                yield from f

        return StreamingResponse(iter_audio(), media_type="audio/mpeg")

    except HTTPException:
        # Re-raise HTTPExceptions directly so FastAPI handles them
        raise
    except Exception as e:
        # Catch any other unexpected errors at the top level
        logging.error(f"Unhandled exception in /speak endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")

# GET /health
@app.get("/health")
async def health_check():
    return {"status": "ok"}