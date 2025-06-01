from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import logging
from fastapi import FastAPI

app = FastAPI(title="Orchestrator Service")


# Microservice endpoints
STT_URL = "http://localhost:8006/transcribe"
LLM_BRIEF_URL = "http://localhost:8005/generate-initial-brief"
API_SERVICE_URL = "http://localhost:8001/get-company-financials"
RETRIEVER_URL = "http://localhost:8003/retrieve"
ANALYSIS_URL = "http://localhost:8004/analyze"
LLM_NARRATIVE_URL = "http://localhost:8005/generate-final-narrative"
TTS_URL = "http://localhost:8007/speak"

logging.basicConfig(level=logging.INFO)

@app.post("/process/")
async def process_request(
    audio_file: UploadFile | None = File(default=None),
    input_text: str | None = Form(default=None),
    response_mode: str = Form(default="audio"),  # "audio" or "text"
    voice: str = Form(default="en-US-AriaNeural")
):
    if audio_file is None and (input_text is None or not input_text.strip()):
        raise HTTPException(status_code=400, detail="Provide either audio_file or input_text.")

    async with httpx.AsyncClient(timeout=60) as client:

        # Step 1: STT if needed
        if audio_file:
            audio_bytes = await audio_file.read()
            files = {"file": (audio_file.filename, audio_bytes, audio_file.content_type)}
            stt_resp = await client.post(STT_URL, files=files)
            if stt_resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"STT error: {stt_resp.text}")
            input_text = stt_resp.json().get("transcription", "").strip()
            if not input_text:
                raise HTTPException(status_code=502, detail="STT returned empty text.")
            logging.info(f"Transcribed input: {input_text}")

        input_text = input_text.strip()
        logging.info(f"User query: {input_text}")

        # Step 2: LLM - Generate Brief & Extract Company Names
        brief_resp = await client.post(LLM_BRIEF_URL, json={"raw_text": input_text})
        if brief_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"LLM brief error: {brief_resp.text}")
        
        brief_data = brief_resp.json()
        brief = brief_data.get("brief", "").strip()
        companies = brief_data.get("company_names", [])

        if not brief or not companies:
            raise HTTPException(status_code=502, detail="LLM brief generation failed or returned empty data.")
        logging.info(f"Generated brief: {brief}...")
        logging.info(f"Companies identified: {companies}")

        # Step 3: Call API service with extracted companies
        if not companies:
            logging.warning("No companies extracted from LLM.")
            raise HTTPException(status_code=400, detail="No companies extracted to process.")

        logging.info(f"Companies extracted: {companies}")

        try:
            api_resp = await client.post(API_SERVICE_URL, json={"companies": companies})
            logging.info(f"API service response status: {api_resp.status_code}")
        except Exception as e:
            logging.error(f"Failed to connect to API service: {e}")
            raise HTTPException(status_code=502, detail="Failed to connect to Company API service.")

        if api_resp.status_code != 200:
            logging.error(f"API service error {api_resp.status_code}: {api_resp.text}")
            raise HTTPException(status_code=502, detail=f"API service error: {api_resp.text}")

        try:
            company_data = api_resp.json().get("company_data", [])
        except Exception as e:
            logging.error(f"Error parsing JSON from API service: {e}")
            raise HTTPException(status_code=502, detail="Invalid response from Company API.")

        logging.info(f"Company data received: {[entry.get('ticker') for entry in company_data]}")

        for entry in company_data:
            if not {"company_name", "ticker", "sector", "region", "history"}.issubset(entry.keys()):
                logging.warning(f"Missing fields in entry: {entry}")


        # Step 3.5: Index docs into retriever
        documents = []
        for entry in company_data:
            if "error" in entry:
                continue
            doc_str = (
                f"{entry['company_name']} ({entry['ticker']}), Sector: {entry['sector']}, "
                f"Region: {entry['region']}. Price history: {entry['history']}"
            )
            documents.append(doc_str)
        index_resp = await client.post(
            f"{RETRIEVER_URL.replace('/retrieve', '')}/index-docs",
            json={"documents": documents}
        )
        if index_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Indexing error: {index_resp.text}")
        logging.info(f"Indexed {len(documents)} documents into retriever")

        # Step 4: Retriever - fetch related chunks
        retriever_resp = await client.post(RETRIEVER_URL, json={"query": input_text, "top_k": 5})
        if retriever_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Retriever error: {retriever_resp.text}")
        context_chunks = retriever_resp.json().get("chunks", [])
        logging.info(f"Retrieved {len(context_chunks)} context chunks")

        # Step 5: Analyzer - extract insights
        analysis_payload = {
            "query": input_text,
            "chunks": context_chunks
        }
        analysis_resp = await client.post(ANALYSIS_URL, json=analysis_payload)
        if analysis_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Analyzer error: {analysis_resp.text}")
        analysis_summary = analysis_resp.json().get("analysis", "")
        logging.info(f"Analysis summary: {analysis_summary[:100]}...")

        # Step 6: LLM - Final Narrative Generation
        narrative_payload = {
            "brief": brief,
            "company_data": company_data,
            "context_chunks": context_chunks,
            "analysis_summary": analysis_summary
        }
        narrative_resp = await client.post(LLM_NARRATIVE_URL, json=narrative_payload)
        if narrative_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Narrative LLM error: {narrative_resp.text}")
        narrative = narrative_resp.json().get("narrative", "").strip()
        if not narrative:
            raise HTTPException(status_code=502, detail="LLM returned empty narrative.")
        logging.info(f"Narrative: {narrative[:150]}...")

        # Step 7: Return as text or synthesize audio
        if response_mode == "text":
            return JSONResponse(content={"narrative": narrative})
        
        file_path = "my_document.txt"
        with open(file_path, "w") as file:
            file.write(narrative)

        # Step 8: TTS
        logging.info(f"Calling TTS service at: {TTS_URL} to stream audio for brief...")

        try:
            # Make the POST request to TTS
            tts_resp = await client.post(
                TTS_URL,
                json={"text": brief, "voice": voice},
                timeout=None  # Required for streaming
            )

            if tts_resp.status_code != 200:
                # Try to parse any error detail for logging and debugging
                try:
                    error_detail = (await tts_resp.aread()).decode()
                except Exception:
                    error_detail = "Unknown error"
                logging.error(f"TTS error: Status {tts_resp.status_code}, Detail: {error_detail}")
                raise HTTPException(status_code=502, detail=f"TTS service returned error {tts_resp.status_code}: {error_detail}")

            logging.info("Returning streaming audio response from TTS service.")
            return StreamingResponse(tts_resp.aiter_bytes(), media_type="audio/mpeg")

        except httpx.RequestError as e:
            logging.error(f"TTS service network error: {e}")
            raise HTTPException(status_code=503, detail=f"Could not connect to TTS service: {e}")

        except Exception as e:
            logging.error(f"Unexpected error during TTS streaming: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Unexpected error during TTS streaming.")