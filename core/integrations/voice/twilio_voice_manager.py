import os
import json
import base64
import asyncio
import audioop
import numpy as np
import edge_tts
from google import genai
from google.genai import types
from typing import Optional, List, Dict
import traceback

class TwilioVoiceManager:
    """
    Manages Twilio voice streams, buffering audio, performing VAD,
    sending to Gemini (STT + generation), and TTS back to Twilio.
    """
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Audio Configuration
        self.SAMPLE_RATE = 8000  # Twilio sends 8kHz mulaw
        self.CHANNELS = 1
        self.CHUNK_SIZE = 160  # 20ms at 8kHz
        
        # VAD Parameters
        self.SILENCE_THRESHOLD = 500  # Amplitude threshold (adjust as needed)
        self.SILENCE_DURATION = 1.5   # Seconds of silence to trigger end of speech
        
        # State
        self.audio_buffer = bytearray()
        self.silence_frames = 0
        self.is_speaking = False
        
        # TTS Voice (Edge TTS)
        self.tts_voice = "en-US-AriaNeural"

    def process_incoming_audio(self, payload: str) -> Optional[bytes]:
        """
        Decodes incoming base64 mulaw audio from Twilio.
        Returns None if buffering (VAD), or returns full PCM bytes if speech ended.
        """
        try:
            # Decode base64
            chunk = base64.b64decode(payload)
            
            # Convert mulaw to PCM (16-bit) for analysis
            pcm_chunk = audioop.ulaw2lin(chunk, 2)
            
            # Analyze energy (RMS)
            rms = audioop.rms(pcm_chunk, 2)
            
            if rms > self.SILENCE_THRESHOLD:
                self.is_speaking = True
                self.silence_frames = 0
                self.audio_buffer.extend(pcm_chunk)
            else:
                if self.is_speaking:
                    self.silence_frames += 1
                    self.audio_buffer.extend(pcm_chunk)
                    
                    # Check if silence duration exceeded
                    # Frame duration = len(pcm_chunk) / 2 bytes / 8000 Hz
                    # Each chunk is usually 20ms (160 samples -> 160 bytes mulaw -> 320 bytes pcm)
                    # 1.5 seconds / 0.02 = 75 frames
                    if self.silence_frames > (self.SILENCE_DURATION * 50): # approx 50 chunks/sec
                        full_audio = self.audio_buffer[:]
                        self.reset_buffer()
                        return full_audio
                
            return None
            
        except Exception as e:
            print(f"[ERROR] Audio processing failed: {e}")
            return None

    def reset_buffer(self):
        self.audio_buffer = bytearray()
        self.silence_frames = 0
        self.is_speaking = False

    async def generate_response(self, pcm_data: bytes, system_instruction: str) -> str:
        """
        Sends PCM audio to Gemini to get a text response.
        Note: Gemini Flash supports audio input directly.
        """
        try:
            # Gemini expects 16kHz or higher usually, but let's try sending the 8kHz PCM directly
            # or upsample it. Upsampling to 16kHz is safer.
            pcm_16k, _ = audioop.ratecv(pcm_data, 2, 1, 8000, 16000, None)
            
            prompt = "Listen to this audio and respond as a helpful concierge assistant."
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    system_instruction,
                    types.Part.from_bytes(data=pcm_16k, mime_type="audio/pcm")
                ]
            )
            return response.text
            
        except Exception as e:
            print(f"[ERROR] Gemini generation failed: {e}")
            traceback.print_exc()
            return "I'm sorry, I couldn't understand that."

    async def text_to_speech(self, text: str) -> bytes:
        """
        Converts text to speech using Edge TTS (free, high quality).
        Returns base64 encoded mulaw audio ready for Twilio.
        """
        try:
            communicate = edge_tts.Communicate(text, self.tts_voice)
            
            # Edge TTS produces MP3. We need to convert to PCM then Mulaw.
            # Using pydub or audioop + ffmpeg usually required.
            # Since we can't easily install ffmpeg in all environments, 
            # we might rely on a temp file and simple wav conversion if possible, 
            # or use a raw stream if Edge supports it.
            
            # For simplicity in this POC, let's accumulate bytes
            mp3_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]
            
            # Convert MP3 to PCM then Mulaw (8kHz)
            # This step requires external tools (ffmpeg) usually.
            # IF ffmpeg is not present, this will fail.
            # Alternative: Use a simpler TTS or just return text for now if environment is restricted.
            
            # Let's assume we can use pydub which wraps ffmpeg
            from pydub import AudioSegment
            import io
            
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2) # 16-bit PCM
            
            pcm_data = audio.raw_data
            mulaw_data = audioop.lin2ulaw(pcm_data, 2)
            
            return base64.b64encode(mulaw_data).decode('utf-8')
            
        except Exception as e:
            print(f"[ERROR] TTS failed: {e}")
            # Fallback or error handling
            return None

# Global instance
_voice_manager = None

def get_voice_manager():
    global _voice_manager
    if not _voice_manager:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             raise ValueError("GEMINI_API_KEY not found")
        _voice_manager = TwilioVoiceManager(api_key)
    return _voice_manager
