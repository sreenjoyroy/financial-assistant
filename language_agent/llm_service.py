from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import datetime
import logging
import os
import json
import re
import requests
import spacy
from dotenv import load_dotenv

load_dotenv()
nlp = spacy.load("en_core_web_sm")

# Setup logging
LOG_FILE = "../logs/usage_logs.json"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

# Initialize FastAPI app
app = FastAPI(title="LLM Service (Mistral via OpenRouter)")

# Environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise EnvironmentError("Missing OPENROUTER_API_KEY environment variable.")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-7b-instruct"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost",
    "X-Title": "Financial Assistant"
}

# Schemas
class InitialBriefRequest(BaseModel):
    raw_text: str

class InitialBriefResponse(BaseModel):
    brief: str
    company_names: List[str]

class FinalNarrativeRequest(BaseModel):
    context_chunks: List[str]
    analysis_summary: Optional[str] = None

class FinalNarrativeResponse(BaseModel):
    narrative: str

def clean_narrative(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    
    # Step 1: Remove markdown artifacts
    text = re.sub(r"[_*~]+", "", text)

    # Step 2: Fix number/letter joins (light touch) - This is the most critical for your issue
    text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Additional aggressive cleaning for concatenated words
    # This pattern looks for a lowercase letter followed by an uppercase letter without a space,
    # or a sequence of letters followed by digits without a space.
    # It attempts to insert a space. This might need fine-tuning.
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # Already there, but emphasized.
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text) # letters followed by digits
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text) # digits followed by letters

    # Step 3: Remove vertical text artifacts
    text = re.sub(r'((?:[a-zA-Z]\n){5,})', lambda m: m.group(0).replace('\n', ''), text)

    # Step 4: Normalize spacing and line breaks
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip()

    # Step 5: Run through spaCy
    doc = nlp(text)
    cleaned_sentences = []

    for sent in doc.sents:
        sentence = sent.text.strip()
        if not sentence:
            continue
        # Capitalize first character safely
        sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
        # Fix punctuation spacing
        sentence = re.sub(r'\s([.,!?;:])', r'\1', sentence)
        sentence = re.sub(r'([.,!?;:])(?=\S)', r'\1 ', sentence)
        cleaned_sentences.append(sentence)

    # Step 6: Join back and extra formatting
    final = ' '.join(cleaned_sentences)
    final = re.sub(r'\s{2,}', ' ', final)
    final = re.sub(r'(\d)\s(%|\$)', r'\1\2', final)  # Remove space in "50 %" or "100 $"

    return final.strip()


# Utility functions
def extract_company_names(text: str) -> List[str]:
    doc = nlp(text)
    return list(set(ent.text for ent in doc.ents if ent.label_ == "ORG"))

def build_initial_prompt(raw_text: str) -> str:
    today = datetime.datetime.now().strftime("%A, %d %B %Y")
    return (
        f"Today is {today}.\n"
        f"Read the following market commentary and provide:\n"
        f"1. A brief 2-3 sentence summary of the market.\n"
        f"2. A list of mentioned companies or stock tickers involved.\n\n"
        f"Text:\n{raw_text.strip()}"
    )

def build_final_prompt(context: List[str], analysis: Optional[str] = None) -> str:
    today = datetime.datetime.now().strftime("%A, %d %B %Y")
    prompt = (
        f"You are a financial analyst assistant. Today is {today}.\n\n"
        f"Using the following market context and analysis, generate a natural-sounding spoken-style summary for a portfolio manager. "
        f"Start generally, then highlight risk in Asia tech stocks and any earnings surprises. "
        f"Keep it concise for text-to-speech. Include numerical data and conclude with a key takeaway.\n\n" # Added 'Keep it concise for text-to-speech' to prompt
    )
    for i, chunk in enumerate(context[:5]):  # Cap to 5
        prompt += f"Context {i+1}: {chunk.strip()}\n"
    if analysis:
        prompt += f"\nAnalytical Summary: {analysis.strip()}\n"
    return prompt

def call_openrouter(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful financial assistant. Ensure your output is clean, readable, and free of concatenated words, especially around numbers and symbols, for text-to-speech conversion."}, # Added instruction to system prompt
        {"role": "user", "content": prompt}
    ]
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": 200
    }
    response = requests.post(OPENROUTER_URL, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logging.error(f"OpenRouter API error [{response.status_code}]: {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"OpenRouter error {response.status_code}: {response.text}"
        )
    else:
        try:
            response_data = response.json()
            llm_output = response_data["choices"][0]["message"]["content"]
            return llm_output
        except KeyError as e:
            logging.error(f"Failed to parse OpenRouter response: Missing key {e} in {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to parse OpenRouter response: {e}")
        except json.JSONDecodeError:
            logging.error(f"Failed to decode OpenRouter response as JSON: {response.text}")
            raise HTTPException(status_code=500, detail=f"OpenRouter response is not valid JSON: {response.text}")

# Routes

@app.post("/generate-initial-brief", response_model=InitialBriefResponse)
async def generate_initial_brief(data: InitialBriefRequest):
    try:
        prompt = build_initial_prompt(data.raw_text)
        response_text = call_openrouter(prompt)
        
        # Apply cleaning to the brief before processing and returning
        cleaned_brief = clean_narrative(response_text) # <-- Apply clean_narrative here
        
        company_names = extract_company_names(cleaned_brief) # Extract from cleaned brief
        
        logging.info(json.dumps({
            "event": "initial_brief",
            "input_chars": len(data.raw_text),
            "company_names": company_names,
            "output_chars": len(cleaned_brief) # Log length of cleaned brief
        }))
        return InitialBriefResponse(brief=cleaned_brief, company_names=company_names) # Return cleaned brief
    except Exception as e:
        logging.error(f"Initial brief generation failed: {str(e)}", exc_info=True) # Added exc_info
        raise HTTPException(status_code=500, detail="Failed to generate initial brief.")

@app.post("/generate-final-narrative", response_model=FinalNarrativeResponse)
async def generate_final_narrative(data: FinalNarrativeRequest):
    try:
        prompt = build_final_prompt(data.context_chunks, data.analysis_summary)
        narrative = call_openrouter(prompt)
        cleaned_narrative = clean_narrative(narrative)
        logging.info(json.dumps({
            "event": "final_narrative",
            "context_len": len(data.context_chunks),
            "analysis_included": bool(data.analysis_summary),
            "output_chars": len(cleaned_narrative) # Log length of cleaned narrative
        }))
        return FinalNarrativeResponse(narrative=cleaned_narrative)
    except Exception as e:
        logging.error(f"Final narrative generation failed: {str(e)}", exc_info=True) # Added exc_info
        raise HTTPException(status_code=500, detail="Failed to generate final narrative.")

@app.get("/health")
async def health_check():
    return {"status": "ok"}