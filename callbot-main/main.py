import time
import os
import json
import base64
import asyncio
import websockets
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlencode
from starlette.websockets import WebSocketState

load_dotenv()

def load_prompt(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    prompt_path = os.path.join(dir_path, 'prompts', f'{file_name}.txt')

    try:
        with open(prompt_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Could not find file: {prompt_path}")
        # Return a default prompt if file is not found
        return "You are a helpful AI assistant from welinate ai to assist people in medical problems. Be professional and helpful in your conversations."

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

NGROK_URL = os.getenv('NGROK_URL')
PORT = int(os.getenv('PORT', 5050))

# Use the real estate system prompt
try:
    SYSTEM_MESSAGE = load_prompt('medical')
except:
    SYSTEM_MESSAGE = "You are a helpful AI assistant from welinate ai to assist people in medical problems. Be professional and helpful in your conversations."

VOICE = 'echo'

# Validation checks
if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
    raise ValueError('Missing Twilio configuration. Please set it in the .env file.')

if not NGROK_URL:
    print("WARNING: NGROK_URL not set. Calls may fail if webhooks can't be reached.")

# FastAPI routes
# Add these imports at the top of your file (if not already present)
from openai import OpenAI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
from typing import Dict, List, Any

# Add this request model for chat messages
class ChatRequest(BaseModel):
    message: str


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# System message configuration
SYSTEM_MESSAGE = load_prompt('medical')
# Chat conversation history storage (in production, use a proper database)
chat_conversations: Dict[str, List[Dict[str, str]]] = {}

# Add this route to handle chat messages using the newer OpenAI client
@app.post("/chat")
async def chat_endpoint(chat_request: ChatRequest):
    try:
        user_message = chat_request.message
        
        # Get or create conversation history for this session
        # In production, you might want to use session IDs or user IDs
        session_id = "default_session"  # You can implement proper session management
        
        if session_id not in chat_conversations:
            chat_conversations[session_id] = [
                {
                    "role": "system", 
                    "content": SYSTEM_MESSAGE
                }
            ]
        
        # Add user message to conversation
        chat_conversations[session_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Make request to OpenAI using the new client
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  # or "gpt-4" if you have access
            messages=chat_conversations[session_id],
            max_tokens=150,
            temperature=0.7,
        )
        
        # Get AI response
        ai_message = response.choices[0].message.content.strip()
        
        # Add AI response to conversation
        chat_conversations[session_id].append({
            "role": "assistant",
            "content": ai_message
        })
        
        # Keep conversation history manageable (last 10 messages)
        if len(chat_conversations[session_id]) > 11:  # system + 10 messages
            chat_conversations[session_id] = [chat_conversations[session_id][0]] + chat_conversations[session_id][-10:]
        
        return JSONResponse(content={"response": ai_message})
        
    except Exception as e:
        error_message = str(e)
        
        # Handle specific OpenAI errors
        if "rate_limit_exceeded" in error_message.lower():
            return JSONResponse(
                content={"response": "I'm experiencing high demand right now. Please try again in a moment."}, 
                status_code=429
            )
        elif "api" in error_message.lower():
            print(f"OpenAI API error: {e}")
            return JSONResponse(
                content={"response": "I'm having trouble connecting right now. Please try again later."}, 
                status_code=500
            )
        else:
            print(f"Chat error: {e}")
            return JSONResponse(
                content={"response": "Sorry, something went wrong. Please try again."}, 
                status_code=500
            )

# Optional: Add a route to clear chat history
@app.post("/chat/clear")
async def clear_chat():
    try:
        session_id = "default_session"
        if session_id in chat_conversations:
            del chat_conversations[session_id]
        return JSONResponse(content={"message": "Chat history cleared"})
    except Exception as e:
        print(f"Error clearing chat: {e}")
        return JSONResponse(content={"error": "Failed to clear chat"}, status_code=500)

# Optional: Add a route to get chat history
@app.get("/chat/history")
async def get_chat_history():
    try:
        session_id = "default_session"
        history = chat_conversations.get(session_id, [])
        # Filter out system messages for the response
        user_history = [msg for msg in history if msg["role"] != "system"]
        return JSONResponse(content={"history": user_history})
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return JSONResponse(content={"error": "Failed to get chat history"}, status_code=500)

# Enhanced version with session management
class ChatRequestWithSession(BaseModel):
    message: str
    session_id: str = "default_session"

@app.post("/chat/session")
async def chat_with_session(chat_request: ChatRequestWithSession):
    try:
        user_message = chat_request.message
        session_id = chat_request.session_id
        
        if session_id not in chat_conversations:
            chat_conversations[session_id] = [
                {
                    "role": "system", 
                    "content": SYSTEM_MESSAGE
                }
            ]
        
        # Add user message to conversation
        chat_conversations[session_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Make request to OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=chat_conversations[session_id],
            max_tokens=150,
            temperature=0.7,
        )
        
        # Get AI response
        ai_message = response.choices[0].message.content.strip()
        
        # Add AI response to conversation
        chat_conversations[session_id].append({
            "role": "assistant",
            "content": ai_message
        })
        
        # Keep conversation history manageable
        if len(chat_conversations[session_id]) > 11:
            chat_conversations[session_id] = [chat_conversations[session_id][0]] + chat_conversations[session_id][-10:]
        
        return JSONResponse(content={
            "response": ai_message,
            "session_id": session_id
        })
        
    except Exception as e:
        error_message = str(e)
        
        if "rate_limit_exceeded" in error_message.lower():
            return JSONResponse(
                content={"response": "I'm experiencing high demand right now. Please try again in a moment."}, 
                status_code=429
            )
        elif "api" in error_message.lower():
            print(f"OpenAI API error: {e}")
            return JSONResponse(
                content={"response": "I'm having trouble connecting right now. Please try again later."}, 
                status_code=500
            )
        else:
            print(f"Chat error: {e}")
            return JSONResponse(
                content={"response": "Sorry, something went wrong. Please try again."}, 
                status_code=500
            )

# Clear specific session
@app.post("/chat/clear/{session_id}")
async def clear_session_chat(session_id: str):
    try:
        if session_id in chat_conversations:
            del chat_conversations[session_id]
        return JSONResponse(content={"message": f"Chat history cleared for session: {session_id}"})
    except Exception as e:
        print(f"Error clearing chat for session {session_id}: {e}")
        return JSONResponse(content={"error": "Failed to clear chat"}, status_code=500)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index3.html", 
        {"request": request, "twilio_number": TWILIO_PHONE_NUMBER}
    )

@app.post("/make-call")
async def make_call(
    request: Request,
    phone_number: str = Form(...),
    starting_text: str = Form(None)
):
    try:
        print(f"Attempting to call: {phone_number}")
        print(f"Using NGROK_URL: {NGROK_URL}")
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        params = {}
        if starting_text:
            params['starting_text'] = starting_text
            
        base_url = f"{NGROK_URL}/outgoing-call"
        url = f"{base_url}?{urlencode(params)}" if params else base_url
        
        print(f"Webhook URL: {url}")
        
        call = client.calls.create(
            url=url,
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            status_callback=f"{NGROK_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed', 'failed', 'busy', 'no-answer'],
            timeout=30,  # Add timeout
            record=False  # Disable recording for privacy
        )
        
        print(f"Call created with SID: {call.sid}")
        
        return templates.TemplateResponse(
            "index3.html",
            {
                "request": request,
                "success": f"Call initiated successfully! Call SID: {call.sid}",
                "twilio_number": TWILIO_PHONE_NUMBER
            }
        )
    except Exception as e:
        print(f"Error creating call: {str(e)}")
        return templates.TemplateResponse(
            "index3.html",
            {
                "request": request,
                "error": f"Error making call: {str(e)}",
                "twilio_number": TWILIO_PHONE_NUMBER
            }
        )

@app.api_route("/outgoing-call", methods=["GET", "POST"])
async def handle_outgoing_call(request: Request):
    print("Outgoing call webhook triggered")
    print(f"Request method: {request.method}")
    
    # Get starting text from query params or form data
    starting_text = request.query_params.get('starting_text')
    print(f"Starting text: {starting_text}")
    
    response = VoiceResponse()
    if starting_text:
        response.say(starting_text, voice='echo')
    else:
        response.say("Hello! This is an AI assistant from welinate ai to assist people in medical problems. how can i assist today in medical field symptoms", voice='echo')
    
    # Get the host from the request
    host = request.headers.get('host') or request.url.hostname
    if not host:
        host = NGROK_URL.replace('https://', '').replace('http://', '') if NGROK_URL else 'localhost:5050'
    
    # Create WebSocket URL
    ws_url = f'wss://{host}/media-stream'
    print(f"WebSocket URL: {ws_url}")
    
    connect = Connect()
    connect.stream(url=ws_url)
    response.append(connect)
    
    print(f"TwiML Response: {str(response)}")
    
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.post("/call-status")
async def call_status_callback(request: Request):
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    call_status = form_data.get('CallStatus')
    call_duration = form_data.get('CallDuration', '0')
    from_number = form_data.get('From')
    to_number = form_data.get('To')
    
    print(f"Call Status Update:")
    print(f"  SID: {call_sid}")
    print(f"  Status: {call_status}")
    print(f"  Duration: {call_duration}")
    print(f"  From: {from_number}")
    print(f"  To: {to_number}")
    
    # Log specific status information
    if call_status == 'failed':
        error_code = form_data.get('ErrorCode')
        error_message = form_data.get('ErrorMessage')
        print(f"  Error Code: {error_code}")
        print(f"  Error Message: {error_message}")
    elif call_status == 'no-answer':
        print("  Call was not answered")
    elif call_status == 'busy':
        print("  Number was busy")
    elif call_status == 'completed':
        print("  Call completed successfully")
    
    return {"status": "success"}

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected to media stream")
    await websocket.accept()

    # Dictionary to store conversation data for call management
    conversation_data = {
        "call_sid": None,
        "last_interaction_time": time.time(),
        "silence_counter": 0,
        "no_interest_signals": 0,
        "input_received": False
    }

    print("Attempting to connect to OpenAI WebSocket API...")
    openai_ws = None
    try:
        # Create a WebSocket connection to OpenAI
        openai_ws = await websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        print("Successfully connected to OpenAI WebSocket API")

        # Send session update
        await send_session_update(openai_ws)

        # Process communication between Twilio and OpenAI
        receive_task = asyncio.create_task(receive_from_twilio(websocket, openai_ws, conversation_data))
        send_task = asyncio.create_task(send_to_twilio(websocket, openai_ws, conversation_data))
        
        # Add a monitoring task to check for inactivity and handle call termination
        monitor_task = asyncio.create_task(monitor_conversation(websocket, openai_ws, conversation_data))
        
        # Wait for all tasks to complete
        await asyncio.gather(receive_task, send_task, monitor_task)
        
    except Exception as e:
        print(f"Failed to connect to OpenAI WebSocket API: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close the OpenAI connection when done if it still exists
        if openai_ws and not openai_ws.closed:
            await openai_ws.close()
            print("OpenAI WebSocket closed")

async def monitor_conversation(websocket, openai_ws, conversation_data):
    """Monitor conversation for inactivity and handle call termination."""
    try:
        while websocket.client_state == WebSocketState.CONNECTED and not openai_ws.closed:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            current_time = time.time()
            time_since_last_interaction = current_time - conversation_data.get("last_interaction_time", current_time)
            
            # If more than 20 seconds of silence or multiple "no interest" signals, end the call
            if ((time_since_last_interaction > 20 and conversation_data.get("input_received", False))
                    or conversation_data.get("no_interest_signals", 0) >= 2):
                
                print("Call ending due to lack of interest or extended silence")
                # Send a prompt for the AI to say goodbye
                goodbye_message = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "text", "text": "[SYSTEM: User is not responding or not interested. Please say goodbye and end the call politely.]"}]
                    }
                }
                if not openai_ws.closed:
                    await openai_ws.send(json.dumps(goodbye_message))
                    await openai_ws.send(json.dumps({"type": "response.create"}))
                
                await asyncio.sleep(5)  # Wait for the AI to respond with goodbye
                
                # Then send hangup signal
                await send_hangup_signal(websocket, conversation_data["call_sid"])
                break
                
            # If there's no activity for a long time, try a prompt
            elif time_since_last_interaction > 30:
                print("Prompting AI for inactivity")
                
                # Reset the timer to avoid multiple prompts
                conversation_data["last_interaction_time"] = current_time
                
                # Send a prompt for the AI to continue the conversation
                prompt_message = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "text", "text": "[SYSTEM: There has been no response from the user. Ask a follow-up question or check if they're still interested.]"}]
                    }
                }
                if not openai_ws.closed:
                    await openai_ws.send(json.dumps(prompt_message))
                    await openai_ws.send(json.dumps({"type": "response.create"}))
                
                # Increment the silence counter
                conversation_data["silence_counter"] += 1
                
                # If too many attempts with no response, end the call
                if conversation_data["silence_counter"] >= 3:
                    print("Call ending after multiple attempts with no response")
                    
                    # Send a prompt for the AI to say goodbye
                    goodbye_message = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "text", "text": "[SYSTEM: No response from user after multiple attempts. Please conclude the call politely.]"}]
                        }
                    }
                    if not openai_ws.closed:
                        await openai_ws.send(json.dumps(goodbye_message))
                        await openai_ws.send(json.dumps({"type": "response.create"}))
                    
                    await asyncio.sleep(5)  # Wait for the AI to respond with goodbye
                    
                    # Then send hangup signal
                    await send_hangup_signal(websocket, conversation_data["call_sid"])
                    break
            
    except Exception as e:
        print(f"Error in monitor_conversation: {e}")
        import traceback
        traceback.print_exc()
        
        # If there's an error, try to send hangup signal
        if conversation_data.get("call_sid"):
            await send_hangup_signal(websocket, conversation_data["call_sid"])

async def receive_from_twilio(websocket, openai_ws, conversation_data):
    """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
    try:
        async for message in websocket.iter_text():
            # Update the last interaction time
            conversation_data["last_interaction_time"] = time.time()
            
            data = json.loads(message)
            if data['event'] == 'media' and not openai_ws.closed:
                audio_append = {
                    "type": "input_audio_buffer.append",
                    "audio": data['media']['payload']
                }
                await openai_ws.send(json.dumps(audio_append))
                
                # Set the flag to indicate input has been received
                conversation_data["input_received"] = True
                
                # Reset the silence counter when we receive input
                conversation_data["silence_counter"] = 0
                
            elif data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                conversation_data["call_sid"] = stream_sid
                print(f"Incoming stream has started {stream_sid}")
                
            elif data['event'] == 'stop':
                stop_sid = data.get('stop', {}).get('streamSid')
                print(f"Stream has stopped: {stop_sid}")
                
                # If stop event received, we need to close connections cleanly
                if not openai_ws.closed:
                    await openai_ws.close()
                
                print("Call stream stopped, ending call session")
                return
                
    except WebSocketDisconnect:
        print("Client disconnected.")
        if not openai_ws.closed:
            await openai_ws.close()
    except Exception as e:
        print(f"Error in receive_from_twilio: {e}")
        import traceback
        traceback.print_exc()

async def send_to_twilio(websocket, openai_ws, conversation_data):
    """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
    session_id = None
    call_completed = False
    
    try:
        async for openai_message in openai_ws:
            if call_completed:
                break
                
            response = json.loads(openai_message)
            event_type = response.get('type', 'unknown')
            
            # Update last interaction time to track AI activity
            conversation_data["last_interaction_time"] = time.time()
            
            if event_type == 'session.created':
                session_id = response['session']['id']
                print(f"Session created with ID: {session_id}")
            
            elif event_type == 'session.updated':
                print("Session updated successfully")
            
            elif event_type == 'response.audio.delta' and response.get('delta'):
                try:
                    audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                    audio_delta = {
                        "event": "media",
                        "streamSid": conversation_data["call_sid"],
                        "media": {
                            "payload": audio_payload
                        }
                    }
                    await websocket.send_json(audio_delta)
                except Exception as e:
                    print(f"Error processing audio data: {e}")
            
            elif event_type == 'conversation.item.created':
                try:
                    item = response.get('item', {})
                    role = item.get('role')
                    content = item.get('content', [])
                    
                    # Process text content for conversation monitoring
                    for content_item in content:
                        if content_item.get('type') == 'text':
                            text = content_item.get('text', '')
                            
                            if role == 'assistant':
                                print(f"Assistant said: {text}")
                                
                                # Check for end of conversation signals
                                end_markers = [
                                    "sorry for the interruption", "thank you for your time", 
                                    "have a good day", "goodbye", "take care", "end this call",
                                    "end of our conversation", "wrap up our call"
                                ]
                                
                                if any(marker in text.lower() for marker in end_markers):
                                    print("End of conversation detected")
                                    
                                    # Allow time for the goodbye message to be processed
                                    await asyncio.sleep(3)
                                    
                                    # Send hang-up signal to Twilio
                                    await send_hangup_signal(websocket, conversation_data["call_sid"])
                                    call_completed = True
                            
                            elif role == 'user':
                                print(f"User said: {text}")
                                
                                # Check for disinterest signals
                                disinterest_markers = [
                                    "not interested", "don't call", "remove me", "stop calling",
                                    "not right now", "busy", "can't talk"
                                ]
                                
                                if any(marker in text.lower() for marker in disinterest_markers):
                                    conversation_data["no_interest_signals"] += 1
                                    print(f"Disinterest signal detected. Count: {conversation_data['no_interest_signals']}")
                            
                except Exception as e:
                    print(f"Error processing conversation item: {e}")
            
            elif event_type == 'response.done':
                try:
                    # Process the response.done content
                    if 'response' in response and 'output' in response['response']:
                        output_items = response['response']['output']
                        
                        for output_item in output_items:
                            if output_item.get('role') == 'assistant' and 'content' in output_item:
                                assistant_content = output_item['content']
                                
                                for content_item in assistant_content:
                                    if content_item.get('type') == 'audio' and 'transcript' in content_item:
                                        content_text = content_item['transcript']
                                        print(f"Found transcript in response.done: {content_text}")
                                        
                                        # Check for end of conversation signals
                                        end_markers = [
                                            "sorry for the interruption", "thank you for your time", 
                                            "have a good day", "goodbye", "take care", "end this call",
                                            "end of our conversation", "wrap up our call"
                                        ]
                                        
                                        if any(marker in content_text.lower() for marker in end_markers):
                                            print("End of conversation detected in response.done")
                                            
                                            # Allow time for the goodbye message to be processed
                                            await asyncio.sleep(3)
                                            
                                            # Send hang-up signal to Twilio
                                            await send_hangup_signal(websocket, conversation_data["call_sid"])
                                            call_completed = True
                                
                except Exception as e:
                    print(f"Error processing response.done: {e}")

    except websockets.exceptions.ConnectionClosed:
        print("OpenAI WebSocket connection closed")
    except Exception as e:
        print(f"Error in send_to_twilio: {e}")
        import traceback
        traceback.print_exc()

async def send_hangup_signal(websocket, call_sid):
    try:
        if not websocket.client_state == WebSocketState.CONNECTED:
            print("WebSocket already disconnected, cannot send hangup signal")
            return False
            
        # Send the hangup event to Twilio
        hangup_message = {
            "event": "hangup",
            "streamSid": call_sid
        }
        await websocket.send_json(hangup_message)
        print(f"Hangup signal sent for call {call_sid}")
        
        # Also send a mark event to ensure Twilio processes the hangup
        mark_message = {
            "event": "mark", 
            "streamSid": call_sid,
            "mark": {
                "name": "call_end"
            }
        }
        await asyncio.sleep(1)

        await websocket.send_json(mark_message)
        print("Mark event sent to finalize call termination")
        
        # Allow a short delay for Twilio to process
        await asyncio.sleep(5)

        # Client-side closure of the WebSocket connection
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(1000, "Call terminated")
            print("WebSocket connection closed")
        
        return True
    except Exception as e:
        print(f"Error sending hangup signal: {e}")
        import traceback
        traceback.print_exc()
        return False

async def send_session_update(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", 'audio'],
            "temperature": 0.8,
        }
    }
    print('Sending session update to OpenAI')
    try:
        await openai_ws.send(json.dumps(session_update))
        print('Session update sent successfully')
    except Exception as e:
        print(f"Error sending session update: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=5050)
