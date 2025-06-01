# 🧠 Multi-Agent Financial Assistant

A voice- and text-enabled financial assistant powered by multi-agent architecture. This system uses speech-to-text, LLM-based reasoning, company data retrieval, and natural language generation — all orchestrated to provide real-time financial insights in text and speech.

---

## 📌 Key Features

- 🎙️ Accepts voice or text prompts
- 🤖 LLM agent to extract relevant companies
- 💹 Retrieves ticker data & market history using `yfinance`
- 📚 Retrieves meaningful financial chunks from historical data
- 🧠 Generates a well-structured financial brief using LLM
- 🔊 Responds in natural-sounding speech using a TTS agent (if user opts for audio)

---

## 🧬 Architecture Overview

                  +-----------------+
      Voice/Text →|  Input Handler  |
                  +-----------------+
                           ↓
 +------------------------ stt_service (Voice Agent) ------------------------+
 |                              (if voice input)                            |
 +-------------------------------------------------------------------------+
                           ↓
                  +-----------------+
                  |  llm_service    | ←-- (Language Agent)
                  +-----------------+
                           ↓
        [Extracts key companies from user intent]
                           ↓
                  +-----------------+
                  | api_service     | ←-- (API Agent)
                  +-----------------+
    [Fetches ticker, sector, region, and historical data via `yfinance`]
                           ↓
                  +----------------------+
                  | retrieve_service     | ←-- (Retriever Agent)
                  +----------------------+
          [Finds most relevant data chunks]
                           ↓
                  +------------------+
                  | Final LLM Call   |
                  +------------------+
         [Generates financial brief/narrative]
                           ↓
+------------------------ tts_service (Voice Agent) ------------------------+
|                              (if audio output required)                   |
+-------------------------------------------------------------------------+

                           ↓
                    📤 Output Display

---

## 🚀 Getting Started

### 1️⃣ Clone the Repo

```bash
git clone https://github.com/YOUR_USERNAME/financial-assistant.git
cd financial-assistant

2️⃣ Install Dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

3️⃣ Setup .env File
# .env

# OpenRouter API for LLM service
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Service URLs
LLM_BRIEF_URL=http://localhost:8001/generate-brief
API_SERVICE_URL=http://localhost:8002/get-company-data
RETRIEVE_URL=http://localhost:8003/retrieve
TTS_SERVICE_URL=http://localhost:8004/speak
STT_SERVICE_URL=http://localhost:8005/transcribe

# Other options
ENABLE_AUDIO=True


4️⃣ Run All Microservices
You can spin up all agents (LLM, API, Retriever, STT, TTS) with a single command using the startup.py script:

python startup.py



🗂️ Project Structure
financial-assistant/
├── agents/
│   ├── voice_agent/
│   │   ├── stt_service.py
│   │   └── tts_service.py
│   ├── language_agent/
│   │   └── llm_service.py
│   ├── api_agent/
│   │   └── api_service.py
│   └── retriever_agent/
│       └── retrieve_service.py
├── startup.py                 # Starts all services at once
├── requirements.txt
├── .env.example
└── README.md

🧪 Sample Input/Output
Input (Voice/Text):

"What is today's market status?"

LLM Output:

"According to the market movement, companies like Tesla, Nvidia, and Apple have seen volatile changes driven by tech sector dynamics..."

Final Output (Text + Audio):

Brief with ticker summaries, sector analysis, and recent movement delivered in voice and/or text.

📌 Tech Stack
Python 3.12+

FastAPI (Microservices)

httpx, uvicorn

yfinance for stock data

OpenRouter LLM API

Optional: gTTS / pyttsx3 / Whisper / ElevenLabs for TTS & STT
