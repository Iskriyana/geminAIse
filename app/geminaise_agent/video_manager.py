import asyncio
import os
import uuid
import time
from typing import Optional
from google import genai

from geminaise_agent.agent import latest_tryon_videos

# Maintain a set of active operation IDs being polled
active_video_operations = set()

def _get_vertex_client() -> genai.Client:
    project = os.getenv("GEMINAISE_GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GEMINAISE_GCP_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return genai.Client(vertexai=True, project=project, location=location)

async def _poll_video_operation(operation_name: str, session_id: str):
    """
    Poll a Veo generate_videos operation until complete.
    Saves the MP4 to static/tryon_videos and registers the URL.
    """
    print(f"[VideoManager] Started polling Veo operation {operation_name} for session {session_id}...")
    try:
        # Run the polling loop in a thread to avoid blocking the asyncio event loop
        # with synchronous API calls.
        def _poll():
            client = _get_vertex_client()
            op = client.operations.get(operation_name)
            while not op.done:
                time.sleep(10)
                op = client.operations.get(operation_name)
            return op

        operation = await asyncio.get_event_loop().run_in_executor(None, _poll)
        
        if operation.result and operation.result.generated_videos:
            video_bytes = operation.result.generated_videos[0].video_bytes
            
            filename = f"{uuid.uuid4()}.mp4"
            filepath = os.path.join(os.path.dirname(__file__), "..", "static", "tryon_videos", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "wb") as f:
                f.write(video_bytes)
                
            video_url = f"/static/tryon_videos/{filename}"
            print(f"[VideoManager] Success! Video saved to {video_url}")
            
            # Register it for the frontend to pick up
            latest_tryon_videos[session_id] = video_url
            
        elif operation.error:
            print(f"[VideoManager] Veo polling failed: {operation.error}")
        else:
            print(f"[VideoManager] Veo polling finished but no video or error was found.")

    except Exception as e:
        print(f"[VideoManager] Error polling video operation {operation_name}: {e}")
    finally:
        active_video_operations.remove(operation_name)


def start_video_polling(operation_name: str, session_id: str):
    """
    Starts an asynchronous background task to poll a Vertex AI video generation
    operation. Does not block the main event loop.
    """
    if operation_name in active_video_operations:
        return
    active_video_operations.add(operation_name)
    asyncio.create_task(_poll_video_operation(operation_name, session_id))
