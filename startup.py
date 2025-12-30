import subprocess
import time
import sys

services = [
    {"name": "API Agent",        "path": "api_agent/api_service.py",       "port": 8001},
    {"name": "Retriever Agent",  "path": "retriever_agent/retriever_service.py", "port": 8003},
    {"name": "Analysis Agent",   "path": "analysis_agent/analysis_service.py", "port": 8004},
    {"name": "LLM Agent",        "path": "language_agent/llm_service.py",  "port": 8005},
    {"name": "Voice STT Agent",  "path": "voice_agent/stt_service.py",     "port": 8006},
    {"name": "Voice TTS Agent",  "path": "voice_agent/tts_service.py",     "port": 8007},
    {"name": "Orchestrator",     "path": "orchestrator/main_router.py",    "port": 8000},
]

processes = []

print("🚀 Launching microservices...\n")

for service in services:
    print(f"Starting {service['name']} on port {service['port']}...")
    proc = subprocess.Popen([
        sys.executable,
        "-m",
        "uvicorn", f"{service['path'].replace('/', '.').replace('.py', '')}:app",
        "--port", str(service["port"]),
        "--reload"
    ])
    processes.append(proc)
    time.sleep(1)  # slight delay to avoid collisions

print("\n✅ All services are starting. Press Ctrl+C to stop them all.")

try:
    for proc in processes:
        proc.wait()
except KeyboardInterrupt:
    print("\n🛑 Shutting down all services...")
    for proc in processes:
        proc.terminate()
