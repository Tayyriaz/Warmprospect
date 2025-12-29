import os
import io
import warnings
import asyncio
import urllib
import traceback
from typing import Tuple, List, Optional
from pathlib import Path

# --- MONKEY PATCH FOR WEBSOCKETS COMPATIBILITY ---
# The google-genai SDK (v0.2.x) calls recv(decode=False) which fails on standard websockets library.
try:
    from websockets.legacy.protocol import WebSocketCommonProtocol
    
    _original_recv = WebSocketCommonProtocol.recv

    async def _patched_recv(self, *args, **kwargs):
        # Remove 'decode' argument if present, as standard websockets.recv() doesn't support it
        kwargs.pop('decode', None) 
        return await _original_recv(self, *args, **kwargs)

    WebSocketCommonProtocol.recv = _patched_recv
    
    # Also patch Protocol for newer websockets versions if needed
    from websockets.protocol import Protocol
    if hasattr(Protocol, 'recv'):
        _original_proto_recv = Protocol.recv
        
        async def _patched_proto_recv(self, *args, **kwargs):
             kwargs.pop('decode', None)
             return await _original_proto_recv(self, *args, **kwargs)
        
        Protocol.recv = _patched_proto_recv

except ImportError:
    pass
# -------------------------------------------------

from google import genai
from dotenv import load_dotenv

import traceback

# Work around missing urllib import in some SDK internals.
if not hasattr(genai, "urllib"):
    genai.urllib = urllib
try:
    from google.genai import _api_client as _api_client
    if not hasattr(_api_client, "urllib"):
        _api_client.urllib = urllib
except Exception:
    pass

# Work around older asyncio loops that don't accept "additional_headers".
_orig_base_create_connection = asyncio.BaseEventLoop.create_connection

async def _patched_create_connection(self, *args, **kwargs):
    kwargs.pop("additional_headers", None)
    return await _orig_base_create_connection(self, *args, **kwargs)

asyncio.BaseEventLoop.create_connection = _patched_create_connection
from google.genai import types

load_dotenv()

# Simple Settings class to mimic app.core.config
class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

settings = Settings()

class VoiceService:
    """
    Service for handling voice interactions using Gemini Live API.
    """
    
    def __init__(self):
        print("[DEBUG] Initializing VoiceService...")
        if not settings.GEMINI_API_KEY:
            print("[ERROR] GEMINI_API_KEY is missing!")
            raise ValueError("GEMINI_API_KEY is not set in environment variables")
        
        masked_key = settings.GEMINI_API_KEY[:4] + "..." + settings.GEMINI_API_KEY[-4:] if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 8 else "***"
        print(f"[DEBUG] VoiceService initialized with API Key: {masked_key}")
        
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Using the specific model version mentioned in the sample
        self.model_name = "gemini-2.0-flash-exp"

    async def convert_to_pcm16_mono_16k(self, file_bytes: bytes) -> bytes:
        """
        Convert arbitrary audio to 16-bit PCM mono 16kHz.
        Strictly uses native wave module. Fails if not a valid WAV or if conversion requires ffmpeg.
        """
        print(f"[DEBUG] convert_to_pcm16_mono_16k input size: {len(file_bytes)} bytes")
        import wave
        import audioop

        # Try processing as native WAV
        try:
            with io.BytesIO(file_bytes) as wav_io:
                with wave.open(wav_io, 'rb') as wav:
                    # Get current properties
                    n_channels = wav.getnchannels()
                    sampwidth = wav.getsampwidth()
                    framerate = wav.getframerate()
                    frames = wav.readframes(wav.getnframes())
                    
                    print(f"[DEBUG] WAV properties: channels={n_channels}, width={sampwidth}, rate={framerate}, frames={len(frames)}")

                    # 1. Convert to Mono if needed
                    if n_channels > 1:
                        frames = audioop.tomono(frames, sampwidth, 1, 0)
                        n_channels = 1

                    # 2. Resample to 16kHz if needed
                    if framerate != 16000:
                        frames, _ = audioop.ratecv(frames, sampwidth, 1, framerate, 16000, None)
                        framerate = 16000

                    # 3. Convert to 16-bit (2 bytes) if needed
                    if sampwidth != 2:
                        frames = audioop.lin2lin(frames, sampwidth, 2)
                        sampwidth = 2
                    
                    print(f"[DEBUG] Conversion complete. Output size: {len(frames)} bytes")
                    return frames
        except (wave.Error, EOFError) as e:
            # Not a valid WAV file
            print(f"[ERROR] Invalid WAV file: {e}")
            raise ValueError("Invalid WAV file. Non-WAV formats (mp3, webm) require ffmpeg which is disabled.")
        except Exception as e:
            print(f"[ERROR] Native WAV conversion failed: {e}")
            traceback.print_exc()
            raise ValueError(f"Audio processing failed: {e}")

    async def call_gemini_live_with_audio(self, pcm_data: bytes) -> Tuple[bytes, List[str]]:
        """
        Open a Live API session, send PCM audio once, collect full audio response,
        and return it as raw 16-bit PCM at 24kHz.
        """
        print(f"[DEBUG] call_gemini_live_with_audio called with {len(pcm_data)} bytes")
        
        # Work around older asyncio loop implementations that don't accept
        # the "additional_headers" kwarg used by some websocket clients.
        loop = asyncio.get_running_loop()
        if not hasattr(loop, "_orig_create_connection"):
            orig_create_connection = loop.create_connection

            async def _create_connection_wrapper(*args, **kwargs):
                kwargs.pop("additional_headers", None)
                return await orig_create_connection(*args, **kwargs)

            loop._orig_create_connection = orig_create_connection
            loop.create_connection = _create_connection_wrapper

        # Create proper Content object for system_instruction
        system_instruction_content = types.Content(
            parts=[types.Part(text="You are a helpful and friendly assistant. Always respond with audio, never text-only. Keep your responses concise and supportive.")]
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],  # Explicitly request AUDIO only
            system_instruction=system_instruction_content,
        )

        response_audio_chunks: List[bytes] = []
        text_responses: List[str] = []

        # Retry logic: Try twice to get audio response
        max_retries = 2
        
        for attempt in range(max_retries):
            print(f"[DEBUG] Connection attempt {attempt+1}/{max_retries}")
            try:
                async with self.client.aio.live.connect(
                    model=self.model_name,
                    config=config,
                ) as session:
                    print(f"[DEBUG] Connected to Gemini Live. Sending audio...")
                    # Create Blob with proper MIME type
                    await session.send(
                        input={"mime_type": "audio/pcm;rate=16000", "data": pcm_data},
                        end_of_turn=True  # Signal that this is the complete user input
                    )
                    
                    # Wait for response with timeout
                    start_time = asyncio.get_event_loop().time()
                    timeout_seconds = 30
                    seen_chunks = set()
                    
                    print(f"[DEBUG] Waiting for response...")
                    try:
                         # The .receive() iterator in version 0.2.2 might have an issue in some environments
                        # We will process messages manually if the async generator fails
                        async for message in session.receive():
                            # Check for audio data in various locations
                            if hasattr(message, 'server_content') and message.server_content:
                                if hasattr(message.server_content, 'model_turn') and message.server_content.model_turn:
                                    if hasattr(message.server_content.model_turn, 'parts'):
                                        for part in message.server_content.model_turn.parts:
                                            # Audio in inline_data
                                            if hasattr(part, 'inline_data') and part.inline_data:
                                                if hasattr(part.inline_data, 'data') and isinstance(part.inline_data.data, bytes):
                                                    chunk_data = part.inline_data.data
                                                    chunk_hash = hash(chunk_data[:100])
                                                    if chunk_hash not in seen_chunks:
                                                        seen_chunks.add(chunk_hash)
                                                        response_audio_chunks.append(chunk_data)
                                                        # print(f"[DEBUG] Received audio chunk: {len(chunk_data)} bytes")
                                            
                                            # Text trace (for debugging)
                                            if hasattr(part, 'text') and part.text:
                                                text_responses.append(part.text[:100])
                                                print(f"[DEBUG] Received text: {part.text[:50]}...")

                                # Direct data on server_content
                                if hasattr(message.server_content, 'data') and message.server_content.data:
                                    if isinstance(message.server_content.data, bytes):
                                        chunk_data = message.server_content.data
                                        chunk_hash = hash(chunk_data[:100])
                                        if chunk_hash not in seen_chunks:
                                            seen_chunks.add(chunk_hash)
                                            response_audio_chunks.append(chunk_data)

                                # Generation complete signal
                                if hasattr(message.server_content, "generation_complete") and message.server_content.generation_complete:
                                    print("[DEBUG] Generation complete signal received.")
                                    await asyncio.sleep(0.5)  # Wait for any trailing chunks
                                    break
                            
                            # Message-level data
                            if hasattr(message, 'data') and message.data is not None:
                                if isinstance(message.data, bytes):
                                    chunk_data = message.data
                                    chunk_hash = hash(chunk_data[:100])
                                    if chunk_hash not in seen_chunks:
                                        seen_chunks.add(chunk_hash)
                                        response_audio_chunks.append(chunk_data)
                            
                            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                                print("[DEBUG] Timeout waiting for response")
                                break

                    except TypeError as type_err:
                         # Ignore decode error from websockets if patched version didn't catch it
                         if "unexpected keyword argument 'decode'" not in str(type_err):
                             print(f"[ERROR] TypeError in receive loop: {type_err}")
                             pass
                         else:
                             print(f"[DEBUG] Ignored expected decode error")
                
                # If we got audio, break the retry loop
                if response_audio_chunks:
                    print(f"[DEBUG] Successfully collected {len(response_audio_chunks)} audio chunks")
                    break
                    
            except Exception as e:
                error_str = str(e).lower()
                if "quota" in error_str or "1011" in error_str or "resource_exhausted" in error_str:
                    print(f"[CRITICAL] Gemini API Quota Exceeded: {e}")
                    # Stop retrying immediately for quota errors
                    raise RuntimeError(f"QUOTA_EXCEEDED: {e}")

                print(f"[ERROR] Error in Gemini Live connection attempt {attempt+1}: {e}")
                traceback.print_exc()
                if attempt == max_retries - 1:
                    # If this was the last attempt, re-raise
                    raise

        if not response_audio_chunks:
            error_msg = "No audio response received from Gemini Live API."
            if text_responses:
                error_msg += f" Text responses received: {text_responses}"
            print(f"[ERROR] {error_msg}")
            raise RuntimeError(error_msg)

        return b"".join(response_audio_chunks), text_responses

    def wrap_pcm24k_to_wav(self, pcm_24k: bytes) -> str:
        """
        Wrap raw 24kHz PCM into a temporary WAV file and return its path.
        """
        from tempfile import NamedTemporaryFile
        import wave

        tmp = NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp.name
        tmp.close()

        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(24000)
            wf.writeframes(pcm_24k)

        return tmp_path

# Lazy initialization
_voice_service_instance = None

def get_voice_service() -> VoiceService:
    global _voice_service_instance
    if _voice_service_instance is None:
        _voice_service_instance = VoiceService()
    return _voice_service_instance

# Global instance for backward compatibility if needed
voice_service = get_voice_service()
