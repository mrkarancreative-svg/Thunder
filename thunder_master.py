import os
import time
import threading
import socket
import requests
import numpy as np
import sounddevice as sd

try:
    import openai_whisper as _openai_whisper
except ImportError:
    try:
        import whisper as _openai_whisper
    except ImportError:
        _openai_whisper = None

import pyttsx3
import customtkinter as ctk
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from google import genai


class WhisperRuntime:
    """Thin adapter around the openai-whisper backend to match the app's expected API."""

    def __init__(self, model_size="base"):
        self.model_size = model_size
        self._backend = _openai_whisper.load_model(model_size)

    def transcribe(self, audio, fp16=False, **kwargs):
        result = _openai_whisper.transcribe(self._backend, audio, fp16=fp16, **kwargs)
        return result if isinstance(result, dict) else {"text": ""}


class whisper:
    """Compatibility wrapper exposing the load_model API used throughout the app."""

    _cache = {}

    @staticmethod
    def load_model(model_size="base"):
        model_size = str(model_size)
        if model_size not in whisper._cache:
            whisper._cache[model_size] = WhisperRuntime(model_size)
        return whisper._cache[model_size]

    @staticmethod
    def transcribe(audio, fp16=False, **kwargs):
        return whisper.load_model().transcribe(audio, fp16=fp16, **kwargs)

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
# Get local IP automatically for network communication
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

LOCAL_IP = get_local_ip()
PORT = 8000

# Initialize FastAPI App for Cross-Device Sync
app = FastAPI(title="Thunder AI Master Server")

# Initialize Google Gemini Client (Ensure GEMINI_API_KEY environment variable is set)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
You are Thunder, an advanced, elite AI assistant connected across the user's laptop, 
phone, and smartwatch. You have access to real-time internet data and local device information. 
Keep your answers sharp, direct, highly accurate, and conversational, optimized for voice output.
"""

gui_reference = None

# API Endpoint used by Phone and Smartwatch
class CommandRequest(BaseModel):
    device: str  # 'phone', 'watch', 'laptop'
    command: str

@app.post("/api/thunder")
async def api_receive_command(req: CommandRequest):
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Empty command.")
    
    try:
        # Query Gemini API with live search context enabled if needed
        prompt = f"[Incoming query from {req.device}]: {req.command}"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'system_instruction': SYSTEM_INSTRUCTION}
        )
        reply = response.text

        # Update Laptop GUI Log in real-time
        if gui_reference:
            gui_reference.append_chat(req.device.upper(), req.command)
            gui_reference.append_chat("THUNDER", reply)
            gui_reference.speak_response(reply)

        return {"status": "success", "device": req.device, "response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_fastapi_server():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")


# ==========================================
# 2. OFFLINE WHISPER SPEECH-TO-TEXT ENGINE
# ==========================================
class WhisperSTT:
    def __init__(self, model_size="base"):
        print("[THUNDER]: Loading Whisper STT model into RAM...")
        self.model = whisper.load_model(model_size)
        self.sample_rate = 16000
        print("[THUNDER]: Whisper STT ready.")

    def record_and_transcribe(self, duration=5):
        audio_data = sd.rec(int(duration * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype='float32')
        sd.wait()
        result = self.model.transcribe(audio_data.flatten(), fp16=False)
        return result.get("text", "").strip()


# ==========================================
# 3. LAPTOP CUSTOMTKINTER GUI INTERFACE
# ==========================================
class ThunderMasterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ THUNDER AI - Hybrid Master Ecosystem")
        self.geometry("560x680")
        ctk.set_appearance_mode("dark")

        # Initialize TTS Engine
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 175)

        # Initialize Whisper
        self.stt = WhisperSTT(model_size="base")

        # --- UI Layout ---
        self.title_label = ctk.CTkLabel(self, text="⚡ THUNDER MASTER HUB", font=("Arial", 22, "bold"))
        self.title_label.pack(pady=10)

        self.network_label = ctk.CTkLabel(
            self, text=f"Local Server Active: http://{LOCAL_IP}:{PORT}", text_color="#00E5FF", font=("Arial", 11)
        )
        self.network_label.pack(pady=2)

        self.status_label = ctk.CTkLabel(self, text="STATUS: READY", text_color="#00FF66", font=("Arial", 12, "bold"))
        self.status_label.pack(pady=5)

        self.chat_log = ctk.CTkTextbox(self, width=500, height=430, font=("Arial", 13))
        self.chat_log.pack(pady=10)
        self.chat_log.configure(state="disabled")

        self.voice_btn = ctk.CTkButton(
            self, text="🎤 Speak to Thunder", command=self.start_voice_thread, width=180, height=40
        )
        self.voice_btn.pack(pady=10)

    def update_status(self, text, color):
        self.status_label.configure(text=f"STATUS: {text}", text_color=color)

    def append_chat(self, sender, text):
        def _update():
            self.chat_log.configure(state="normal")
            self.chat_log.insert("end", f"[{sender}]: {text}\n\n")
            self.chat_log.see("end")
            self.chat_log.configure(state="disabled")
        self.after(0, _update)

    def speak_response(self, text):
        self.append_chat("THUNDER", text)
        self.update_status("SPEAKING...", "#00FF66")
        self.tts.say(text)
        self.tts.runAndWait()
        self.update_status("READY", "#00FF66")

    def start_voice_thread(self):
        threading.Thread(target=self._process_voice_pipeline, daemon=True).start()

    def _process_voice_pipeline(self):
        self.update_status("LISTENING...", "#00E5FF")
        user_text = self.stt.record_and_transcribe(duration=5)

        if not user_text:
            self.update_status("READY", "#00FF66")
            return

        self.append_text_gui("YOU", user_text)
        self.update_status("THINKING (Gemini AI + Internet)...", "#FF9900")

        # Local shortcut management
        command_lower = user_text.lower()
        if "open browser" in command_lower or "open chrome" in command_lower:
            reply = "Opening Google Chrome."
            os.system("start chrome" if os.name == "nt" else "open -a 'Google Chrome'")
        elif "time" in command_lower:
            reply = f"The current system time is {time.strftime('%I:%M %p')}."
        else:
            try:
                # Query Gemini Cloud AI (with live internet capabilities)
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_text,
                    config={'system_instruction': SYSTEM_INSTRUCTION}
                )
                reply = response.text
            except Exception as e:
                reply = "I encountered a network issue reaching my cloud intelligence network."

        self.speak_response(reply)

    def append_text_gui(self, sender, text):
        self.append_chat(sender, text)


# ==========================================
# 4. APPLICATION LAUNCHER
# ==========================================
if __name__ == "__main__":
    # Start FastAPI server in a background thread
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()

    # Launch Laptop Desktop UI
    app = ThunderMasterApp()
    gui_reference = app
    app.mainloop()