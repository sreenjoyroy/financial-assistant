import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import httpx
import tempfile
import os
from io import BytesIO
import asyncio
import nest_asyncio

nest_asyncio.apply()

ORCHESTRATOR_URL = "http://localhost:8000/process/"

st.set_page_config(page_title="📈 Morning Market Brief Assistant", page_icon="📊")

st.title("📊 Morning Market Brief Assistant")

st.markdown("""
Get an **AI-generated summary** of the financial market by providing **voice** or **text** input.

Choose between **audio playback** or **text summary** as the output.
""")

input_mode = st.radio("Choose input mode:", ["Voice", "Text"])
response_mode = st.radio("Choose output format:", ["Audio", "Text"])

voice_options = {
    "Aria (US Female)": "en-US-AriaNeural",
    "Guy (US Male)": "en-US-GuyNeural",
    "Jenny (UK Female)": "en-GB-JennyNeural",
    "Ryan (UK Male)": "en-GB-RyanNeural",
}
voice = st.selectbox("Select voice for audio response:", list(voice_options.keys()))

audio_bytes = None
input_text = None

if input_mode == "Voice":
    st.info("🎙 Click Start to record your voice. Click Stop when you're done.")

    ctx = webrtc_streamer(
        key="speech",
        mode=WebRtcMode.SENDRECV,
        media_stream_constraints={"audio": True, "video": False},
        audio_receiver_size=1024,
        async_processing=True
    )

    if ctx.audio_receiver:
        try:
            audio_frames = ctx.audio_receiver.get_frames(timeout=2)
            if audio_frames:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                    for frame in audio_frames:
                        tmpfile.write(frame.to_ndarray().tobytes())
                    tmpfile_path = tmpfile.name
                with open(tmpfile_path, "rb") as f:
                    audio_bytes = f.read()
                os.unlink(tmpfile_path)
            else:
                st.warning("No audio received yet. Try recording again.")
        except Exception as e:
            st.error(f"Audio capture error: {e}")

else:
    input_text = st.text_area("Type your financial market query here:", height=150)

if st.button("🧠 Get Market Brief"):
    if input_mode == "Voice" and not audio_bytes:
        st.error("No audio recorded. Please try again.")
        st.stop()

    if input_mode == "Text" and (not input_text or not input_text.strip()):
        st.error("Text input cannot be empty.")
        st.stop()

    payload = {
        "response_mode": response_mode.lower(),
        "voice": voice_options[voice]
    }

    async def send_request():
        async with httpx.AsyncClient(timeout=90) as client:
            if input_mode == "Voice":
                files = {"audio_file": ("query.wav", audio_bytes, "audio/wav")}
                resp = await client.post(ORCHESTRATOR_URL, files=files, data=payload)
            else:
                data = {"input_text": input_text, **payload}
                resp = await client.post(ORCHESTRATOR_URL, data=data)

            resp.raise_for_status()
            return resp

    with st.spinner("🧠 Processing your request... please wait..."):
        try:
            loop = asyncio.get_event_loop()
            response = loop.run_until_complete(send_request())
        except Exception as e:
            st.error(f"❌ Request failed: {e}")
            st.stop()

    # Handle the response
    if response_mode == "Text":
        result = response.json()
        narrative = result.get("narrative", "")
        if narrative:
            st.subheader("📄 Market Summary")
            st.write(narrative)
        else:
            st.warning("No narrative generated.")
    else:
        st.subheader("🔊 AI-Synthesized Audio")
    
    # --- START DEBUGGING ADDITIONS ---
    print(f"DEBUG: Entering audio display block.")
    print(f"DEBUG: Response status code: {response.status_code}")
    print(f"DEBUG: Response headers: {response.headers}")
    
    audio_data = None
    if hasattr(response, 'content'): # For 'requests' or httpx.response.read()
        audio_data = response.content
        print(f"DEBUG: Received audio data via 'response.content'.")
    elif hasattr(response, 'read'): # For async httpx.response if not already awaited
        try:
            # If using an async client like httpx, you might need to await reading the content
            # Streamlit runs synchronously, so if you're making an async call, ensure it's awaited.
            # For 'requests' library, .content is already populated.
            # If you are using httpx within an async context:
            # audio_data = await response.read() 
            # print(f"DEBUG: Received audio data via 'response.read()'.")
            
            # For simplicity with typical Streamlit sync execution with 'requests':
            pass # content is already populated
        except Exception as e:
            print(f"DEBUG: Error reading audio content: {e}")
            st.error(f"Error reading audio content: {e}")
    else:
        print(f"DEBUG: Response object does not have 'content' or 'read' attribute for audio data.")
        st.error("Could not retrieve audio data from the response object.")

    if audio_data:
        print(f"DEBUG: Type of audio_data: {type(audio_data)}")
        print(f"DEBUG: Length of audio_data: {len(audio_data)} bytes")
        
        # Optionally save the received audio to a file for manual inspection
        debug_filename = "streamlit_received_audio_debug.mp3"
        try:
            with open(debug_filename, "wb") as f:
                f.write(audio_data)
            print(f"DEBUG: Saved received audio to '{debug_filename}' for inspection.")
        except Exception as e:
            print(f"DEBUG: Error saving debug audio file: {e}")

        if len(audio_data) > 0:
            st.audio(audio_data, format="audio/mpeg")
            st.success("Audio player should be visible above.")
        else:
            st.error("Received empty audio data. The backend likely generated no audio or the stream was broken.")
            # Show headers to help debug
            st.code(f"Response Status: {response.status_code}\nResponse Headers: {response.headers}")
    else:
        st.error("No audio data was retrieved from the response. This indicates an issue with the backend response or client handling.")
        st.code(f"Response Status: {response.status_code}\nResponse Headers: {response.headers}")
    # --- END DEBUGGING ADDITIONS ---