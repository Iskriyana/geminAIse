# geminAIse

Real-time, voice-driven AI personal shopper and virtual stylist built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/).

## Inspiration

Online shopping offers endless choices but lacks the personalized, tactile, and immediate feedback of an in-store fitting room. The traditional "text box and search bar" paradigm can be disrupted via the new agentic capabilities. I wanted to build an experience that feels like having a high-end personal stylist in your living room—someone you can talk to naturally, who understands your style, and who can instantly show you exactly how an outfit will look on your body.

More importantly, the Multimodal Live API has always fascinated me. I have always wanted to try it, and this hackathon was the perfect trigger. Combining multimodality, live real-time interactions, and autonomous agents brings together a lot of aspects that I am passionate about in the AI space. I built geminAIse trying to bridge the gap between imagination and reality in e-commerce, moving beyond static chatbots into a fully immersive experience.

*Disclaimer: I would have loved to have more time—it was such a cool challenge! Due to other urgent topics, I could only work on this for about 3 days, primarily with AI assistance. Nevertheless, I wanted to submit my work, be it imperfect, because it is such a cool challenge.*

## What it does

**geminAIse** is a real-time, voice-driven AI personal shopper and virtual stylist.

- **Conversational commerce:** Users converse naturally with the agent using their voice. The agent can be interrupted, understands context, and provides tailored fashion advice based on a product catalogue.
- **Virtual try-on:** Users upload a photo of themselves, and when they ask to try on a specific item from the catalogue, the agent seamlessly generates a photorealistic image of the user wearing the item—preserving their facial identity, pose, and body type. Future developments include generating a video.

## How I built it

I built geminAIse leveraging the Google Agent Development Kit (ADK) and Google Cloud Platform.

- **The brain (live agent):** I utilised the `gemini-2.5-flash-native-audio-preview` model via the Google ADK to handle real-time, bidirectional audio streaming. The agent is orchestrated with a custom FastAPI backend using WebSockets to manage the live audio feed and interruptible conversations.
- **Semantic product search:** To map natural language queries (e.g., "I want something cozy for the beach") to the product catalogue, I pre-computed embeddings for the inventory using `gemini-embedding-2-preview`. When a user asks for an item, I find the best match using cosine similarity:

  $$\text{similarity} = \cos(\theta) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$$

- **Visual generation:** For the virtual try-on, I use `gemini-3.1-flash-image-preview`. I engineered specific prompts that take the user's source image and the product image, instructing the model to dress the user while strictly preserving their features.
- **Infrastructure:** The backend is hosted on Google Cloud, utilizing Vertex AI and Google AI Studio endpoints for the multimodal generation.

## Challenges I ran into

Building a real-time, multimodal architecture in 3 days came with significant hurdles:

1. **Concurrency and WebSockets:** Handling real-time WebSocket audio streams concurrently with long-running image generation tasks was tricky. Initially, the heavy image generation blocked the `asyncio` event loop, causing `1006 keepalive ping timeout` crashes and dropping the user's call. I solved this by offloading the generation tasks to background threads (`run_in_executor`).
2. **State management:** Orchestrating the state between the Live API (audio), the frontend UI (displaying images dynamically), and the background generation tasks required a robust session management system.
3. **Live video generation:** It takes time, it is tricky when people are involved. For now unresolved, but I will continue working on it.

## Accomplishments that I'm proud of

I am happy about working with ADK Gemini Live AI Toolkit and combining it with Flash Image 3.1 into a single, cohesive user experience. The moment I first asked the agent for a jacket, heard it reply instantly, and watched my own photo update with the new clothes was magical. Achieving this level of multimodal orchestration as a solo developer in just a few days is a testament to the power of the ADK and modern AI tooling.

## What I learned

- **The power of the ADK:** I learned how to effectively use the Google Agent Development Kit to manage complex tool-calling and multimodal routing.
- **Asynchronous Python:** I started learning about FastAPI, WebSockets, and managing background tasks in Python to ensure a buttery-smooth user experience.

## What's next for geminAIse

Because of the short timeframe, there are so many exciting features I still want to build. My next steps include:

- **Enhanced functionalities:**
  - Adding more products and product attributes to the catalogue.
  - Supporting trying on *more than one product* at a time (e.g., generating a full outfit with a shirt and pants simultaneously).
- **Advanced styling:** Enabling the agent to proactively recommend other complementary products and curate complete styles based on user preferences.
- **Being able to produce videos**
- **Deployment on Google Cloud Run**
- **Robustness & scale:**
  - Implementing proper evaluation frameworks to measure agent accuracy and hallucination rates.
  - Improving concurrency handling for multiple simultaneous users.
- **Platform expansion:** Building a dedicated phone app to make the voice and camera experience even more seamless.

## Running locally (spin-up)

1. Copy `.env.example` to `.env` and set `GOOGLE_CLOUD_PROJECT` (and region if needed). Add any keys your setup requires (for example a Gemini API key where the app expects it).
2. For Vertex-backed features (e.g. embeddings), authenticate with Application Default Credentials, e.g. `gcloud auth application-default login`.
3. Install Python dependencies for the FastAPI / ADK app (see `uv.lock` if you use `uv`), then from the `app` directory run: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
4. Optional: build and run with the root `Dockerfile` (expects dependency metadata at the repo root as referenced in that file).

The web UI is served at `/try-on` (the app root redirects there).
