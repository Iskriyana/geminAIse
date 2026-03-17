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

def _poll_single(operation_name: str):
    client = _get_vertex_client()
    return client.operations.get(operation_name)

async def _poll_video_operation(operation_name: str, session_id: str):
    """
    Poll a Veo generate_videos operation until complete.
    Saves the MP4 to static/tryon_videos and registers the URL.
    """
    print(f"[VideoManager] Started polling Veo operation {operation_name} for session {session_id}...")
    try:
        # Initial check
        op = await asyncio.to_thread(_poll_single, operation_name)
        
        while not getattr(op, 'done', False):
            await asyncio.sleep(10)  # Async sleep so we don't block the thread pool
            op = await asyncio.to_thread(_poll_single, operation_name)
        
        # When done, we need to get the final result structure.
        # Sometimes the `done` status is true but the result isn't fully unpacked by the SDK
        if hasattr(op, 'result') and getattr(op.result, 'generated_videos', None):
            video_bytes = op.result.generated_videos[0].video_bytes
            
            filename = f"{uuid.uuid4()}.mp4"
            filepath = os.path.join(os.path.dirname(__file__), "..", "static", "tryon_videos", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "wb") as f:
                f.write(video_bytes)
                
            video_url = f"/static/tryon_videos/{filename}"
            print(f"[VideoManager] Success! Video saved to {video_url}")
            
            # Register it for the frontend to pick up
            from geminaise_agent.agent import latest_tryon_videos
            latest_tryon_videos[session_id] = video_url
            
        elif getattr(op, 'error', None):
            print(f"[VideoManager] Veo polling failed: {op.error}")
        else:
            print(f"[VideoManager] Veo polling finished but no video or error was found. Full op: {op}")

    except Exception as e:
        import traceback
        print(f"[VideoManager] Error polling video operation {operation_name}: {e}")
        traceback.print_exc()
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
