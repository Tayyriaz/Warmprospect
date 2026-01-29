"""
Voice API routes for handling voice interactions.
"""

import os
import re
from fastapi import APIRouter, Request, HTTPException, File, UploadFile, WebSocket
from fastapi.responses import FileResponse, Response
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client as TwilioClient
from core.integrations.voice import get_voice_service, get_voice_manager

router = APIRouter()

# Base system instruction for voice
BASE_SYSTEM_INSTRUCTION = """
You are an AI concierge for this specific business. You act as an always-on front desk to capture leads and share information from the business's own Knowledge Base or provided context.
Tone: warm, upbeat, human, joyful; use contractions and light positivity. Ask one question per turn and end with a friendly CTA.
Do not use bullets in replies.

Allowed HTML: <b> <i> <u> <br> <code> <a> only. Knowledge first—never guess.
Collect/share minimum PII; verify and E.164-format phone before creating a deal or booking any appointment.
Never reveal tool/API/action names or internal strings. Do not offer services that don't exist in tools or provided business context.
Use memory; NEVER repeat a question the user already answered.
"""


@router.post("/api/voice/chat")
async def voice_chat(file: UploadFile = File(...)):
    """
    Accepts an audio file (e.g., from Flutter or browser), sends it to Gemini Live,
    and returns a WAV audio response.
    
    The input audio is converted to the format Gemini expects (16kHz PCM),
    and the response is converted back to a standard WAV file (24kHz).
    """
    print("[DEBUG] /api/voice/chat endpoint hit")
    try:
        print(f"[DEBUG] Received file: {file.filename}, content_type: {file.content_type}")
        file_bytes = await file.read()
        print(f"[DEBUG] File size: {len(file_bytes)} bytes")
        
        if not file_bytes:
            print("[ERROR] Empty audio file received")
            raise HTTPException(status_code=400, detail="Empty audio file.")

        # Check if it's already PCM (e.g. from browser conversion) or needs conversion
        pcm_16k = None
        if file.content_type == "audio/pcm" or (file.filename and file.filename.endswith(".pcm")):
            print("[DEBUG] File identified as raw PCM")
            pcm_16k = file_bytes
            # Validate PCM format (even length)
            if len(pcm_16k) % 2 != 0:
                print(f"[ERROR] Invalid PCM format: length {len(pcm_16k)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid PCM format: data length ({len(pcm_16k)} bytes) is not even."
                )
        else:
            # Convert generic audio (mp3, wav, webm, etc.) to PCM
            try:
                print("[DEBUG] Attempting conversion to PCM16 Mono 16k")
                voice_service = get_voice_service()
                pcm_16k = await voice_service.convert_to_pcm16_mono_16k(file_bytes)
                print(f"[DEBUG] Conversion successful. PCM size: {len(pcm_16k)} bytes")
            except ValueError as ve:
                # Specific error for invalid WAV format (e.g. WebM sent when only WAV supported)
                print(f"[ERROR] ValueError during conversion: {ve}")
                raise HTTPException(status_code=400, detail=str(ve))
            except Exception as conv_err:
                print(f"[ERROR] Unexpected conversion error: {conv_err}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Audio conversion failed: {str(conv_err)}"
                ) from conv_err

        # Call Gemini Live
        try:
            print("[DEBUG] Calling Gemini Live service...")
            voice_service = get_voice_service()
            pcm_24k, text_responses = await voice_service.call_gemini_live_with_audio(pcm_16k)
            print(f"[DEBUG] Gemini Live response received. Audio size: {len(pcm_24k)} bytes. Text responses: {len(text_responses)}")
        except RuntimeError as gemini_err:
            error_str = str(gemini_err)
            print(f"[ERROR] Gemini Live runtime error: {error_str}")
            
            if "QUOTA_EXCEEDED" in error_str or "resource_exhausted" in error_str.lower():
                raise HTTPException(
                    status_code=429,
                    detail="Gemini API Quota Exceeded. The AI service is currently unavailable due to high usage limits. Please try again later or upgrade the API key."
                )
            
            raise HTTPException(status_code=503, detail=f"Voice service unavailable: {error_str}") from gemini_err

        # Wrap raw PCM in WAV container for easy playback
        print("[DEBUG] Wrapping PCM response in WAV container")
        wav_path = voice_service.wrap_pcm24k_to_wav(pcm_24k)
        print(f"[DEBUG] WAV file created at: {wav_path}")
        
        return FileResponse(
            wav_path,
            media_type="audio/wav",
            filename="response.wav",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CRITICAL] Unexpected error in voice endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error processing voice request.")


@router.post("/make-call")
async def make_call(request: Request):
    """
    Initiates an outgoing call to the specified phone number.
    """
    try:
        data = await request.json()
        phone_number = data.get("phone_number")
        
        if not phone_number:
            raise HTTPException(status_code=400, detail="Phone number is required")

        # Twilio Configuration
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([account_sid, auth_token, from_number]):
             raise HTTPException(status_code=500, detail="Twilio credentials not configured")

        client = TwilioClient(account_sid, auth_token)
        
        # Construct the webhook URL for the call flow
        # Use NGROK URL if provided, otherwise construct from request host
        ngrok_url = os.getenv("NGROK_URL")
        if ngrok_url:
            # Validate and sanitize ngrok URL
            host = ngrok_url.replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
        else:
            # Validate host header to prevent injection
            host_header = request.headers.get('host', '')
            # Allow only alphanumeric, dots, dashes, and colons (for port)
            if re.match(r'^[a-zA-Z0-9.\-:]+$', host_header):
                host = host_header.split(":")[0]  # Remove port if present
            else:
                raise HTTPException(status_code=400, detail="Invalid host header")
        
        # We'll use the /voice/incoming endpoint logic for the outgoing call's TwiML
        # But since client.calls.create takes a URL, we need the full public URL.
        webhook_url = f"https://{host}/voice/incoming"
        
        print(f"[DEBUG] Initiating call to {phone_number} with webhook {webhook_url}")

        call = client.calls.create(
            to=phone_number,
            from_=from_number,
            url=webhook_url
        )

        return {"success": True, "call_sid": call.sid, "message": "Call initiated"}

    except Exception as e:
        print(f"[ERROR] Make call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/incoming")
async def voice_incoming(request: Request):
    """
    Twilio webhook for incoming calls.
    Returns TwiML to start a Media Stream (WebSocket).
    """
    # Get NGROK URL or Host from request
    host = request.headers.get('host')
    
    response = VoiceResponse()
    response.say("Hello, connecting you to the concierge assistant.", voice='alice')
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Handles bidirectional audio: Twilio -> Buffer/VAD -> Gemini -> TTS -> Twilio.
    """
    import json
    await websocket.accept()
    print("[DEBUG] WebSocket connected: /media-stream")
    
    voice_manager = get_voice_manager()
    stream_sid = None
    
    # Simple conversation loop state
    system_instruction = BASE_SYSTEM_INSTRUCTION
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                print(f"[DEBUG] Media Stream started: {stream_sid}")
                
            elif data['event'] == 'media':
                payload = data['media']['payload']
                
                # Process audio chunk (VAD & Buffer)
                full_audio = voice_manager.process_incoming_audio(payload)
                
                if full_audio:
                    print(f"[DEBUG] Speech detected! Processing {len(full_audio)} bytes...")
                    
                    # 1. Send Audio to Gemini (STT + Generation)
                    # Note: We are sending raw PCM bytes. Gemini Flash handles audio input.
                    response_text = await voice_manager.generate_response(
                        full_audio, 
                        system_instruction
                    )
                    print(f"[DEBUG] Gemini Response: {response_text}")
                    
                    if response_text:
                        # 2. TTS (Text to Audio)
                        audio_payload = await voice_manager.text_to_speech(response_text)
                        
                        if audio_payload:
                            # 3. Send Audio back to Twilio
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            })
                            
            elif data['event'] == 'stop':
                print(f"[DEBUG] Media Stream stopped: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        print("[DEBUG] WebSocket disconnected")
    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")
        import traceback
        traceback.print_exc()
