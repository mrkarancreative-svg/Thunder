import os
import requests
import pyttsx3
import customtkinter as ctk

# Point to your Render Cloud URL once deployed (or use http://127.0.0.1:8000 for local testing)
SERVER_URL = "https://thunder-ai-core.onrender.com/api/thunder"

class ThunderLaptopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ THUNDER AI - Master Laptop Hub")
        self.geometry("520x620")
        ctk.set_appearance_mode("dark")

        # Initialize Text-to-Speech Engine
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 175)

        # --- GUI Layout ---
        self.title_label = ctk.CTkLabel(self, text="⚡ THUNDER AI HUB", font=("Arial", 22, "bold"))
        self.title_label.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="STATUS: CONNECTED TO CLOUD", text_color="#00FF66", font=("Arial", 12, "bold"))
        self.status_label.pack(pady=5)

        self.chat_log = ctk.CTkTextbox(self, width=460, height=430, font=("Arial", 13))
        self.chat_log.pack(pady=10)
        self.chat_log.configure(state="disabled")

        self.entry = ctk.CTkEntry(self, width=350, placeholder_text="Ask Thunder anything...")
        self.entry.pack(side="left", padx=(30, 10), pady=15)
        self.entry.bind("<Return>", lambda event: self.send_command())

        self.send_btn = ctk.CTkButton(self, text="Send", width=90, command=self.send_command)
        self.send_btn.pack(side="left", pady=15)

    def append_chat(self, sender, text):
        def _update():
            self.chat_log.configure(state="normal")
            self.chat_log.insert("end", f"[{sender}]: {text}\n\n")
            self.chat_log.see("end")
            self.chat_log.configure(state="disabled")
        self.after(0, _update)

    def speak_response(self, text):
        self.append_chat("THUNDER", text)
        self.tts.say(text)
        self.tts.runAndWait()

    def send_command(self):
        query = self.entry.get().strip()
        if not query:
            return
        
        self.append_chat("YOU", query)
        self.entry.delete(0, "end")

        try:
            payload = {"device": "laptop", "command": query}
            res = requests.post(SERVER_URL, json=payload, timeout=15)
            
            if res.status_code == 200:
                reply = res.json()["response"]
                self.speak_response(reply)
            else:
                self.append_chat("ERROR", "Server returned an error response.")
        except Exception as e:
            self.append_chat("ERROR", f"Could not reach cloud server: {str(e)}")

if __name__ == "__main__":
    app = ThunderLaptopApp()
    app.mainloop()