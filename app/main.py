import os
from pathlib import Path
from dotenv import load_dotenv

# Force Google AI Studio endpoints instead of Vertex AI for Live API
if "GOOGLE_CLOUD_PROJECT" in os.environ:
    del os.environ["GOOGLE_CLOUD_PROJECT"]
if "GOOGLE_CLOUD_LOCATION" in os.environ:
    del os.environ["GOOGLE_CLOUD_LOCATION"]

load_dotenv(Path(__file__).parent.parent / ".env")

# Ensure they are cleared even after load_dotenv in case they are in the .env file
if "GOOGLE_CLOUD_PROJECT" in os.environ:
    del os.environ["GOOGLE_CLOUD_PROJECT"]
if "GOOGLE_CLOUD_LOCATION" in os.environ:
    del os.environ["GOOGLE_CLOUD_LOCATION"]

# Explicitly set the API version to v1alpha for Live API support
os.environ["GEMINI_API_VERSION"] = "v1alpha"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from google.adk.agents.live_request_queue import LiveRequestQueue
import json
import asyncio
import base64
import logging
import uuid
from google import genai

from geminaise_agent.agent import root_agent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# Explicitly initialize the client to force Google AI Studio
client = genai.Client(http_options={'api_version': 'v1alpha'})
session_service = InMemorySessionService()
runner = Runner(app_name="geminaise_agent", agent=root_agent, session_service=session_service)

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/try-on")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="")

@app.get("/try-on", response_class=HTMLResponse)
async def get_ui():
    with open("templates/index.html", "r") as f:
        return f.read()

@app.post("/apps/geminaise_agent/users/{user_id}/sessions")
async def create_sess(user_id: str):
    session_id = str(uuid.uuid4())
    await session_service.create_session(app_name="geminaise_agent", user_id=user_id, session_id=session_id)
    return {"id": session_id}

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    await websocket.accept()
    
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig()
    )
    
    live_request_queue = LiveRequestQueue()
    
    async def upstream_task():
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                audio_blob = types.Blob(mime_type="audio/pcm;rate=16000", data=message["bytes"])
                live_request_queue.send_realtime(audio_blob)
            elif "text" in message:
                text_data = message["text"]
                json_message = json.loads(text_data)
                
                if json_message.get("type") == "image":
                    image_data = base64.b64decode(json_message["data"])
                    image_blob = types.Blob(mime_type="image/jpeg", data=image_data)
                    live_request_queue.send_realtime(image_blob)
                    
                    # Store the latest image for this session so the try_on tool can use it
                    from geminaise_agent.agent import latest_user_images
                    latest_user_images[session_id] = image_data

                    # Force the agent to explicitly acknowledge the image to prevent dropping the connection
                    content = types.Content(parts=[
                        types.Part(text="[SYSTEM MESSAGE: The user has just uploaded a photo of themselves. You MUST now use the try_on_apparel tool to generate an image of them wearing the requested clothes. Do not ask for permission, just call the tool.]")
                    ])
                    live_request_queue.send_content(content)


                elif json_message.get("type") == "text":
                    content = types.Content(parts=[types.Part(text=json_message["text"])])
                    live_request_queue.send_content(content)

    async def downstream_task():
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config
        ):
            event_json = event.model_dump_json(exclude_none=True, by_alias=True)
            await websocket.send_text(event_json)

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except WebSocketDisconnect:
        logger.debug("Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        live_request_queue.close()
