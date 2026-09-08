import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
import tinytuya

app = FastAPI(title="Thunder AI Central Intelligence Server")

# Initialize Gemini AI Client (Picks up GEMINI_API_KEY from Render Environment Variables)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
You are Thunder, an advanced, elite AI assistant connected across the user's laptop, 
phone, and smartwatch. You have access to real-time internet data and local device information. 
CRITICAL RULE: Your response will be read aloud via text-to-speech. Keep answers sharp, direct, 
highly accurate, and conversational, completely free of markdown formatting or filler text.
"""

# Smart Home Configuration (Update with your local Tuya device details if applicable)
SMART_CONFIG = {
    "device_id": "YOUR_DEVICE_ID_HERE",
    "ip": "YOUR_BULB_IP_HERE",
    "local_key": "YOUR_LOCAL_KEY_HERE"
}

class CommandRequest(BaseModel):
    device: str  # 'phone', 'watch', 'laptop'
    command: str

def control_smart_lights(command: str):
    """Executes local smart home light actions based on text commands."""
    command = command.lower()
    try:
        if not SMART_CONFIG["device_id"] or SMART_CONFIG["device_id"] == "YOUR_DEVICE_ID_HERE":
            return None # Skip if not configured yet
            
        bulb = tinytuya.BulbDevice(SMART_CONFIG["device_id"], SMART_CONFIG["ip"], SMART_CONFIG["local_key"])
        bulb.set_version(3.3)
        
        if "turn on" in command or "lights on" in command:
            bulb.turn_on()
            return "Turning the lights on now."
        elif "turn off" in command or "lights off" in command:
            bulb.turn_off()
            return "Turning the lights off."
        elif "blue light" in command or "set lights blue" in command:
            bulb.set_colour(0, 0, 255)
            return "Setting lights to blue."
    except Exception as e:
        return f"Failed to control smart light: {str(e)}"
    
    return None

@app.get("/")
def home():
    return {"status": "Thunder AI Core Server is Online"}

@app.post("/api/thunder")
async def process_command(req: CommandRequest):
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty.")
    
    try:
        # Step 1: Check if command is a smart home action
        light_reply = control_smart_lights(req.command)
        if light_reply:
            reply = light_reply
        else:
            # Step 2: Pass query to Gemini Cloud Brain with internet capabilities
            prompt = f"[Incoming query from {req.device}]: {req.command}"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'system_instruction': SYSTEM_INSTRUCTION}
            )
            reply = response.text

        return {
            "status": "success",
            "device": req.device,
            "query": req.command,
            "response": reply
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))