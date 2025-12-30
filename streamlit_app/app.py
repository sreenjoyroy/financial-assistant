import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import httpx
import tempfile
import os
from io import BytesIO
import asyncio
import nest_asyncio
from datetime import datetime
import json

nest_asyncio.apply()

ORCHESTRATOR_URL = "http://localhost:8000/process/"

# Initialize session state for stats
if 'total_sessions' not in st.session_state:
    st.session_state.total_sessions = 0
if 'total_queries' not in st.session_state:
    st.session_state.total_queries = 0
if 'voice_queries' not in st.session_state:
    st.session_state.voice_queries = 0
if 'text_queries' not in st.session_state:
    st.session_state.text_queries = 0
if 'session_started' not in st.session_state:
    st.session_state.session_started = True
    st.session_state.total_sessions += 1

# Page config with custom theme
st.set_page_config(
    page_title="📈 Morning Market Brief Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
        padding: 0.75rem;
        border-radius: 8px;
        border: none;
        font-size: 1.1rem;
    }
    .stButton>button:hover {
        background-color: #1557a0;
    }
    .info-box {
        background-color: #e8f4f8;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 8px;
        border-left: 5px solid #28a745;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Sidebar configuration
with st.sidebar:
    st.image("https://via.placeholder.com/200x80/1f77b4/ffffff?text=Market+Brief", use_container_width=True)
    st.markdown("### ⚙️ Configuration")
    
    # Input mode selection
    st.markdown("#### 🎯 Input Method")
    input_mode = st.radio(
        "How would you like to provide your query?",
        ["🎤 Voice Input", "⌨️ Text Input"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Output format selection
    st.markdown("#### 📤 Output Format")
    response_mode = st.radio(
        "Choose your preferred output:",
        ["🔊 Audio Playback", "📝 Text Summary", "🎭 Both"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Voice selection
    st.markdown("#### 🗣️ Voice Settings")
    voice_options = {
        "Aria (US Female)": "en-US-AriaNeural",
        "Guy (US Male)": "en-US-GuyNeural",
        "Jenny (UK Female)": "en-GB-JennyNeural",
        "Ryan (UK Male)": "en-GB-RyanNeural",
    }
    voice = st.selectbox("Select narrator voice:", list(voice_options.keys()))
    
    # Audio quality settings
    audio_quality = st.select_slider(
        "Audio quality:",
        options=["Standard", "High", "Premium"],
        value="High"
    )
    
    st.markdown("---")
    
    # Additional options
    st.markdown("#### 🔧 Advanced Options")
    include_timestamps = st.checkbox("Include timestamps", value=True)
    auto_play = st.checkbox("Auto-play audio", value=True)
    show_debug = st.checkbox("Show debug info", value=False)
    
    st.markdown("---")
    st.markdown("##### 📊 Quick Stats")
    
    # Calculate session stats
    session_change = "+1" if st.session_state.total_sessions > 0 else "0"
    query_change = f"+{st.session_state.total_queries}" if st.session_state.total_queries > 0 else "0"
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Sessions", st.session_state.total_sessions, session_change)
    with col2:
        st.metric("Queries", st.session_state.total_queries, query_change)
    
    # Additional stats in expander
    with st.expander("📈 Detailed Stats"):
        st.markdown(f"**🎤 Voice Queries:** {st.session_state.voice_queries}")
        st.markdown(f"**⌨️ Text Queries:** {st.session_state.text_queries}")
        if st.session_state.total_queries > 0:
            voice_pct = (st.session_state.voice_queries / st.session_state.total_queries) * 100
            st.progress(voice_pct / 100)
            st.caption(f"Voice: {voice_pct:.1f}% | Text: {100-voice_pct:.1f}%")
        
        # Reset button
        if st.button("🔄 Reset Stats", use_container_width=True):
            st.session_state.total_queries = 0
            st.session_state.voice_queries = 0
            st.session_state.text_queries = 0
            st.rerun()

# Main content area
st.markdown('<p class="main-header">📊 Morning Market Brief Assistant</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Get AI-powered financial market insights through voice or text</p>', unsafe_allow_html=True)

# Display current date and market status
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"📅 **Date:** {datetime.now().strftime('%B %d, %Y')}")
with col2:
    st.markdown(f"🕐 **Time:** {datetime.now().strftime('%I:%M %p')}")
with col3:
    market_status = "🟢 Markets Open" if 9 <= datetime.now().hour < 16 else "🔴 Markets Closed"
    st.markdown(f"**Status:** {market_status}")

st.markdown("---")

# Create tabs for better organization
tab1, tab2, tab3 = st.tabs(["📥 Input", "📊 Results", "ℹ️ About"])

audio_bytes = None
input_text = None

with tab1:
    if "🎤" in input_mode:
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown("### 🎙️ Voice Input Mode")
        st.markdown("""
        **Instructions:**
        1. Click the **Start** button below to begin recording
        2. Speak your market query clearly into your microphone
        3. Click **Stop** when you're finished
        4. Review and submit your query
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            ctx = webrtc_streamer(
                key="speech",
                mode=WebRtcMode.SENDRECV,
                media_stream_constraints={"audio": True, "video": False},
                audio_receiver_size=1024,
                async_processing=True
            )
        
        with col2:
            st.markdown("### 🎚️ Status")
            if ctx.audio_receiver:
                st.success("🔴 Recording...")
            else:
                st.info("⚪ Ready")

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
                    st.success("✅ Audio captured successfully!")
                else:
                    st.warning("⏳ Waiting for audio input...")
            except Exception as e:
                st.error(f"❌ Audio capture error: {e}")

    else:
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown("### ⌨️ Text Input Mode")
        st.markdown("Type your market query below. You can ask about:")
        st.markdown("- 📈 Stock market trends\n- 💱 Currency movements\n- 🏦 Economic indicators\n- 📰 Market news and analysis")
        st.markdown('</div>', unsafe_allow_html=True)
        
        input_text = st.text_area(
            "Your market query:",
            height=200,
            placeholder="Example: What are the latest trends in the S&P 500? How is the tech sector performing today?",
            help="Enter your financial market question or request for analysis"
        )
        
        # Character counter
        if input_text:
            char_count = len(input_text)
            st.caption(f"✍️ Characters: {char_count}")

    st.markdown("---")
    
    # Submit button with enhanced styling
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit_button = st.button("🧠 Generate Market Brief", use_container_width=True)

with tab2:
    st.markdown("### 📊 Your Market Brief Results")
    
    if submit_button:
        # Validation
        if "🎤" in input_mode and not audio_bytes:
            st.error("❌ No audio recorded. Please record your voice query first.")
            st.stop()

        if "⌨️" in input_mode and (not input_text or not input_text.strip()):
            st.error("❌ Text input cannot be empty. Please enter your query.")
            st.stop()

        # Update query stats
        st.session_state.total_queries += 1
        if "🎤" in input_mode:
            st.session_state.voice_queries += 1
        else:
            st.session_state.text_queries += 1

        # Prepare payload
        response_mode_value = "audio" if "🔊" in response_mode else "text"
        if "🎭" in response_mode:
            response_mode_value = "both"
            
        payload = {
            "response_mode": response_mode_value,
            "voice": voice_options[voice],
            "quality": audio_quality.lower(),
            "include_timestamps": include_timestamps
        }

        async def send_request():
            async with httpx.AsyncClient(timeout=90) as client:
                if "🎤" in input_mode:
                    files = {"audio_file": ("query.wav", audio_bytes, "audio/wav")}
                    resp = await client.post(ORCHESTRATOR_URL, files=files, data=payload)
                else:
                    data = {"input_text": input_text, **payload}
                    resp = await client.post(ORCHESTRATOR_URL, data=data)
                resp.raise_for_status()
                return resp

        # Progress indicator
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        with st.spinner(""):
            progress_text.text("🔄 Connecting to market data...")
            progress_bar.progress(25)
            
            try:
                loop = asyncio.get_event_loop()
                progress_text.text("📡 Processing your request...")
                progress_bar.progress(50)
                
                response = loop.run_until_complete(send_request())
                
                progress_text.text("✨ Generating your brief...")
                progress_bar.progress(75)
                
                progress_bar.progress(100)
                progress_text.text("✅ Complete!")
                
            except Exception as e:
                st.error(f"❌ Request failed: {e}")
                if show_debug:
                    st.exception(e)
                st.stop()

        # Clear progress indicators
        progress_text.empty()
        progress_bar.empty()

        # Display results
        if "📝" in response_mode or "🎭" in response_mode:
            try:
                result = response.json()
                narrative = result.get("narrative", "")
                if narrative:
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.markdown("#### 📄 Market Summary")
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown(narrative)
                    
                    # Download button for text
                    st.download_button(
                        label="💾 Download Summary",
                        data=narrative,
                        file_name=f"market_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.warning("⚠️ No narrative generated.")
            except:
                pass

        if "🔊" in response_mode or "🎭" in response_mode:
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.markdown("#### 🔊 Audio Playback")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if show_debug:
                st.code(f"Status: {response.status_code}\nHeaders: {response.headers}")
            
            audio_data = response.content if hasattr(response, 'content') else None
            
            if audio_data and len(audio_data) > 0:
                st.audio(audio_data, format="audio/mpeg", autoplay=auto_play)
                
                # Download button for audio
                st.download_button(
                    label="💾 Download Audio",
                    data=audio_data,
                    file_name=f"market_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                    mime="audio/mpeg"
                )
                
                if show_debug:
                    st.success(f"✅ Audio data: {len(audio_data)} bytes")
            else:
                st.error("❌ No audio data received from backend.")
    else:
        st.info("👈 Configure your settings and submit a query to see results here.")

with tab3:
    st.markdown("### ℹ️ About This Application")
    st.markdown("""
    This **Morning Market Brief Assistant** helps you stay informed about financial markets through:
    
    - 🎤 **Voice Queries**: Natural language voice input
    - ⌨️ **Text Queries**: Traditional text-based queries
    - 🔊 **Audio Briefs**: AI-narrated market summaries
    - 📝 **Text Reports**: Detailed written analysis
    
    #### 🎯 Features:
    - Multiple voice options for personalized experience
    - Flexible input/output modes
    - Real-time market data processing
    - High-quality audio synthesis
    
    #### 🔒 Privacy:
    Your queries are processed securely and are not stored permanently.
    
    #### 📞 Support:
    For issues or feedback, contact: bijoyroykgp2@gmail.com
    """)

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("🔒 **Secure** | End-to-end encryption")
with col2:
    st.markdown("⚡ **Fast** | Real-time processing")
with col3:
    st.markdown("🎯 **Accurate** | AI-powered insights")