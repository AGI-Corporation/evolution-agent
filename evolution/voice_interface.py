# evolution/voice_interface.py
# Voice-interactive coding agent: mic capture, Whisper STT, GPT-4o code gen, OpenAI TTS

import json
import os
import tempfile
from datetime import datetime

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False

try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    _openai_client = None


class VoiceCodingAgent:
    """
    A voice-interactive coding agent.

    Workflow:
      1. Press Enter to start recording.
      2. Speech is transcribed via OpenAI Whisper.
      3. GPT-4o generates code (or a conversational reply) from the request.
      4. The explanation is read back via OpenAI TTS.
      5. Generated code is displayed and optionally saved to disk.
    """

    SAMPLE_RATE = 16000          # Hz – Whisper works well at 16 kHz
    TTS_SAMPLE_RATE = 24000      # Hz – OpenAI PCM TTS output rate
    DEFAULT_RECORD_SECONDS = 10  # seconds per push-to-talk press

    SYSTEM_PROMPT = (
        "You are an expert Python developer and voice coding assistant. "
        "When a user asks you to write, fix, or explain code, respond with valid JSON "
        "using exactly this schema:\n"
        '{"explanation": "<brief spoken summary>", '
        '"filename": "<suggested_filename.py or null>", '
        '"code": "<complete Python source or null>"}\n'
        "Keep explanations concise (1-3 sentences) because they will be spoken aloud. "
        "If the request is conversational (not about code), set filename and code to null."
    )

    def __init__(self, project_root: str, record_seconds: int = DEFAULT_RECORD_SECONDS):
        self.project_root = project_root
        self.record_seconds = record_seconds
        self.client = _openai_client
        self.conversation_history: list[dict] = []

        if not AUDIO_AVAILABLE:
            print(
                "[VoiceAgent] WARNING: Audio libraries (sounddevice, soundfile, numpy) "
                "are not installed. Run: pip install sounddevice soundfile numpy\n"
                "[VoiceAgent] Falling back to text-only mode."
            )
        if self.client is None:
            print(
                "[VoiceAgent] WARNING: OpenAI client not available. "
                "Set OPENAI_API_KEY and install openai>=1.0.0."
            )

    # ------------------------------------------------------------------
    # Audio I/O helpers
    # ------------------------------------------------------------------

    def listen(self) -> "np.ndarray | None":
        """Record audio from the default microphone."""
        if not AUDIO_AVAILABLE:
            return None
        print(f"[VoiceAgent] Recording for {self.record_seconds}s... (speak now)")
        audio = sd.rec(
            int(self.record_seconds * self.SAMPLE_RATE),
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        print("[VoiceAgent] Recording complete.")
        return audio

    def transcribe(self, audio_array: "np.ndarray") -> str:
        """Convert a float32 numpy audio array to text using OpenAI Whisper."""
        if self.client is None:
            raise RuntimeError("OpenAI client is not available.")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sf.write(tmp_path, audio_array, self.SAMPLE_RATE)
            with open(tmp_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
        finally:
            os.unlink(tmp_path)

        return transcript.text.strip()

    def speak(self, text: str) -> None:
        """Convert text to speech and play it (OpenAI TTS, PCM output)."""
        if self.client is None or not text.strip():
            return

        # Request raw 16-bit PCM so we can play without a decoder
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="pcm",
        )
        if not AUDIO_AVAILABLE:
            # No playback possible; just acknowledge
            print(f"[VoiceAgent] (TTS) {text}")
            return

        audio_data = (
            np.frombuffer(response.content, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        sd.play(audio_data, samplerate=self.TTS_SAMPLE_RATE)
        sd.wait()

    # ------------------------------------------------------------------
    # Code generation
    # ------------------------------------------------------------------

    def generate_code(self, request: str) -> dict:
        """
        Send the user request to GPT-4o and return a structured result dict:
          {"explanation": str, "filename": str | None, "code": str | None}
        """
        if self.client is None:
            return {
                "explanation": "OpenAI client is not configured.",
                "filename": None,
                "code": None,
            }

        self.conversation_history.append({"role": "user", "content": request})

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *self.conversation_history,
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": content})

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"explanation": content, "filename": None, "code": None}

    # ------------------------------------------------------------------
    # File persistence
    # ------------------------------------------------------------------

    def save_code(self, code: str, filename: str) -> str:
        """Write generated code to the project root. Returns the full path."""
        filepath = os.path.join(self.project_root, filename)
        parent_dir = os.path.dirname(filepath)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(code)
        return filepath

    def queue_feature(self, name: str, description: str) -> bool:
        """
        Append a feature request to evolution/feature_queue.json so the Supervisor
        can pick it up in its next evolution cycle.

        Returns True if the feature was successfully queued.
        """
        queue_path = os.path.join(self.project_root, "evolution", "feature_queue.json")
        try:
            if os.path.exists(queue_path):
                with open(queue_path, "r") as f:
                    queue = json.load(f)
            else:
                queue = []

            entry = {
                "name": name,
                "description": description,
                "source": "voice_agent",
                "queued_at": datetime.now().isoformat(),
            }
            queue.append(entry)

            with open(queue_path, "w") as f:
                json.dump(queue, f, indent=2)

            print(f"[VoiceAgent] Feature queued for evolution: '{name}'")
            return True
        except Exception as exc:
            print(f"[VoiceAgent] Failed to queue feature: {exc}")
            return False

    def log_session_entry(self, request: str, result: dict) -> None:
        """Append a session entry to logs/voice_session.log."""
        log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "voice_session.log")
        entry = {
            "timestamp": datetime.now().isoformat(),
            "request": request,
            "explanation": result.get("explanation", ""),
            "filename": result.get("filename"),
            "code_lines": len(result.get("code", "").splitlines()) if result.get("code") else 0,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Main interactive loop
    # ------------------------------------------------------------------

    def _get_input_text(self) -> str:
        """Capture input: voice if audio is available, else keyboard."""
        if AUDIO_AVAILABLE:
            prompt = "Press Enter to speak, or type your request and press Enter: "
            raw = input(prompt)
            if raw.strip():
                return raw.strip()
            audio = self.listen()
            if audio is None:
                return ""
            return self.transcribe(audio)
        else:
            return input("Type your coding request: ").strip()

    def run(self) -> None:
        """Start the voice coding agent interactive loop."""
        print("\n[VoiceAgent] Voice Coding Agent started.")
        print("[VoiceAgent] Project root:", self.project_root)
        print('[VoiceAgent] Say "quit", "exit", or "goodbye" to stop.\n')

        greeting = "Hello! I'm your voice coding assistant. Tell me what you'd like me to code."
        print(f"[VoiceAgent] {greeting}")
        self.speak(greeting)

        while True:
            try:
                user_text = self._get_input_text()
            except (KeyboardInterrupt, EOFError):
                print("\n[VoiceAgent] Interrupted. Goodbye!")
                self.speak("Goodbye!")
                break

            if not user_text:
                self.speak("I didn't catch that. Please try again.")
                continue

            print(f"[VoiceAgent] Request: {user_text}")

            # Exit commands — match whole words to avoid false positives
            if any(
                kw in user_text.lower().split()
                for kw in ("quit", "exit", "goodbye", "bye")
            ):
                self.speak("Goodbye! Happy coding!")
                print("[VoiceAgent] Session ended.")
                break

            # Generate code / response
            try:
                result = self.generate_code(user_text)
            except Exception as exc:
                msg = f"I encountered an error: {exc}"
                print(f"[VoiceAgent] {msg}")
                self.speak("I encountered an error. Please try again.")
                continue

            explanation = result.get("explanation") or "Here is what I came up with."
            code = result.get("code")
            filename = result.get("filename") or "generated_code.py"

            # Speak the explanation
            print(f"[VoiceAgent] {explanation}")
            self.speak(explanation)

            # Log the session
            self.log_session_entry(user_text, result)

            # Display and optionally save the generated code
            if code:
                print(f"\n{'─' * 60}")
                print(f"  {filename}")
                print(f"{'─' * 60}")
                print(code)
                print(f"{'─' * 60}\n")

                try:
                    save_choice = input("Save this code to disk? [y/N]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    break

                if save_choice == "y":
                    try:
                        saved_path = self.save_code(code, filename)
                        msg = f"Code saved to {filename}."
                        print(f"[VoiceAgent] Saved: {saved_path}")
                        self.speak(msg)

                        # Offer to queue the saved file as an evolution feature request
                        try:
                            queue_choice = input(
                                "Queue this as an evolution feature request? [y/N]: "
                            ).strip().lower()
                        except (KeyboardInterrupt, EOFError):
                            break

                        if queue_choice == "y":
                            feature_name = filename.replace(".py", "").replace("_", " ").replace("/", " ")
                            self.queue_feature(
                                name=feature_name,
                                description=f"Implement code generated by voice request: {user_text}",
                            )
                            self.speak(f"Feature '{feature_name}' added to the evolution queue.")
                    except OSError as exc:
                        print(f"[VoiceAgent] Failed to save: {exc}")
                        self.speak("I could not save the file.")
