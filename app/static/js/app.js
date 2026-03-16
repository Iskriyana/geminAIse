import { startAudioPlayerWorklet } from "./audio-player.js";

let websocket;
let audioRecorderContext;
let audioPlayerContext;
let audioWorkletNode;
let audioPlayerNode;
let mediaStream;
let cameraStream;
let isRecording = false;
let isAgentSpeaking = false;
let agentSpeakingTimeout = null;

// UI Elements
const messagesDiv = document.getElementById('messages');
const micBtn = document.getElementById('mic-btn');
const cameraBtn = document.getElementById('camera-btn');
const captureBtn = document.getElementById('capture-btn');
const cameraPreview = document.getElementById('camera-preview');
const capturedImage = document.getElementById('captured-image');

// Add message to chat log
function addMessage(text, type) {
    const p = document.createElement('div');
    p.className = `message ${type}-message`;
    p.textContent = text;
    messagesDiv.appendChild(p);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Convert Float32Array to 16-bit PCM for Gemini
function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
}

// Convert Base64 string to ArrayBuffer for the AudioWorklet
function base64ToArrayBuffer(base64) {
    try {
        // The ADK sometimes sends base64 strings with padding missing or URL-safe characters
        // First, make it standard base64 by replacing URL-safe chars
        let standardBase64 = base64.replace(/-/g, '+').replace(/_/g, '/');

        // Add padding if necessary
        while (standardBase64.length % 4) {
            standardBase64 += '=';
        }

        const binaryString = window.atob(standardBase64);
        const len = binaryString.length;

        // The PCM player expects 16-bit integers, so we need to ensure the byte length is even
        // If it's odd, we drop the last byte to prevent the "byte length of Int16Array should be a multiple of 2" error
        const validLen = len % 2 === 0 ? len : len - 1;

        const bytes = new Uint8Array(validLen);
        for (let i = 0; i < validLen; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Ensure we explicitly return an ArrayBuffer that is a multiple of 2 bytes
        return bytes.buffer.slice(0, validLen);
    } catch (e) {
        console.error("Failed to decode base64 audio data:", e, "Base64 string snippet:", base64.substring(0, 50));
        return new ArrayBuffer(0);
    }
}

// Convert ArrayBuffer to Base64 string
function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}


async function stopRecording() {
    isRecording = false;
    micBtn.textContent = "Start Microphone";
    micBtn.classList.remove("active");
    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
    }
    if (audioWorkletNode) audioWorkletNode.disconnect();
    if (audioPlayerNode) audioPlayerNode.disconnect();
    if (websocket) {
        websocket.close();
    }
    addMessage("Disconnected from geminAIse.", "system");
}

async function startRecording() {
    if (isRecording) {
        stopRecording();
        return;
    }

    // Create a new session via HTTP POST to the ADK backend
    addMessage("Initializing session...", "system");
    const response = await fetch('/apps/geminaise_agent/users/local_user/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    });

    if (!response.ok) {
        addMessage(`Failed to create session: ${response.statusText}`, "system");
        stopRecording();
        return;
    }

    const sessionData = await response.json();
    const sessionId = sessionData.id;

    // Connect to the custom FastAPI WebSocket endpoint
    const wsUrl = `ws://${window.location.host}/ws/local_user/${sessionId}`;
    websocket = new WebSocket(wsUrl);

    websocket.onopen = async () => {
        isRecording = true;
        micBtn.textContent = "Stop Microphone";
        micBtn.classList.add("active");
        addMessage("Connected! Listening...", "system");

        // Start playback via ADK player worklet
        if (!audioPlayerContext) {
            try {
                const [pNode, pCtx] = await startAudioPlayerWorklet();
                audioPlayerNode = pNode;
                audioPlayerContext = pCtx;
            } catch (e) {
                console.error("Failed to start audio player", e);
            }
        }

        // Ensure the audio context is running (browsers sometimes suspend it)
        if (audioPlayerContext && audioPlayerContext.state === 'suspended') {
            await audioPlayerContext.resume();
        }

        // Start MIC
        audioRecorderContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        const source = audioRecorderContext.createMediaStreamSource(mediaStream);

        try {
            // Use absolute URL for the worklet to avoid path resolution issues
            const workletUrl = window.location.origin + '/static/js/audio-worklet.js?v=' + new Date().getTime();
            await audioRecorderContext.audioWorklet.addModule(workletUrl);
            audioWorkletNode = new AudioWorkletNode(audioRecorderContext, 'audio-processor');

            audioWorkletNode.port.onmessage = (event) => {
                if (websocket.readyState === WebSocket.OPEN) {
                    // Convert Float32Array from worklet to Int16Array for the API
                    let float32Array = event.data;

                    // If the agent is speaking, send silence (zeros) instead of actual mic input
                    // This prevents echo loops but keeps the audio stream continuous for the VAD
                    if (isAgentSpeaking) {
                        float32Array = new Float32Array(float32Array.length); // Array of zeros
                    }

                    const pcmBuffer = floatTo16BitPCM(float32Array);

                    // Send directly as binary data, which is what the backend expects
                    websocket.send(pcmBuffer);
                }
            };

            source.connect(audioWorkletNode);
            audioWorkletNode.connect(audioRecorderContext.destination);
            console.log("Microphone successfully connected to worklet");
        } catch (e) {
            console.error("Failed to load audio worklet:", e);
            addMessage("Error loading microphone processor. Audio input may not work.", "system");
        }
    };

    let textBuffer = "";
    let displayedImages = new Set();

    websocket.onmessage = (event) => {
        const adkEvent = JSON.parse(event.data);

        // Handle normal content (text and audio)
        if (adkEvent.content && adkEvent.content.parts) {
            for (const part of adkEvent.content.parts) {
                if (part.text && part.text.trim().length > 0) {
                    textBuffer += part.text;

                    // Check for image URL in the accumulated buffer
                    const urlRegex = /\/static\/tryon_images\/[a-zA-Z0-9-]+\.jpg/g;
                    const matches = textBuffer.match(urlRegex);

                    if (matches) {
                        for (const imageUrl of matches) {
                            if (!displayedImages.has(imageUrl)) {
                                displayedImages.add(imageUrl);

                                // Display the image
                                const img = document.createElement('img');
                                img.src = imageUrl;
                                img.className = 'agent-image';
                                img.style.maxWidth = '100%';
                                img.style.borderRadius = '8px';
                                img.style.marginTop = '10px';

                                const p = document.createElement('div');
                                p.className = `message agent-message`;
                                p.appendChild(img);
                                messagesDiv.appendChild(p);
                                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                            }
                        }
                    }

                    addMessage(part.text, adkEvent.author === 'user' ? 'user' : 'agent');
                }

                // Handle audio (base64 encoded in JSON)
                if (part.inlineData) {
                    if (part.inlineData.mimeType && part.inlineData.mimeType.startsWith("audio/")) {
                        console.log("Received audio chunk!");

                        // Mute the microphone while the agent is speaking to prevent echo loops
                        isAgentSpeaking = true;
                        clearTimeout(agentSpeakingTimeout);
                        agentSpeakingTimeout = setTimeout(() => {
                            isAgentSpeaking = false;
                        }, 1000); // Unmute 1 second after the last audio chunk arrives

                        if (audioPlayerNode) {
                            audioPlayerNode.port.postMessage(base64ToArrayBuffer(part.inlineData.data));
                        }
                    } else if (part.inlineData.mimeType && part.inlineData.mimeType.startsWith("image/")) {
                        // Handle image returned by the agent
                        const img = document.createElement('img');
                        img.src = `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`;
                        img.className = 'agent-image';
                        img.style.maxWidth = '100%';
                        img.style.borderRadius = '8px';
                        img.style.marginTop = '10px';

                        const p = document.createElement('div');
                        p.className = `message agent-message`;
                        p.appendChild(img);
                        messagesDiv.appendChild(p);
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                } else if (part.inline_data) {
                    if (part.inline_data.mime_type && part.inline_data.mime_type.startsWith("audio/")) {
                        console.log("Received audio chunk (snake_case)!");
                        if (audioPlayerNode) {
                            audioPlayerNode.port.postMessage(base64ToArrayBuffer(part.inline_data.data));
                        }
                    }
                }
            }
        }

        // Log tool calls
        if (adkEvent.tool_calls) {
            for (const call of adkEvent.tool_calls) {
                if (call.function_calls) {
                    for (const fc of call.function_calls) {
                        addMessage(`Agent is calling tool: ${fc.name} with args ${JSON.stringify(fc.args)}`, "system");
                    }
                }
            }
        }
    };

    websocket.onerror = (e) => {
        console.error("WS Error", e);
        addMessage("Connection error occurred.", "system");
        stopRecording();
    }
}

micBtn.addEventListener("click", startRecording);

// Camera and Image Capture Logic
cameraBtn.addEventListener("click", async () => {
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null;
        cameraPreview.style.display = "none";
        captureBtn.style.display = "none";
        cameraBtn.textContent = "Open Camera";
        return;
    }

    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 768 }, height: { ideal: 768 } }
        });
        cameraPreview.srcObject = cameraStream;
        cameraPreview.style.display = "block";
        captureBtn.style.display = "block";
        capturedImage.style.display = "none";
        cameraBtn.textContent = "Close Camera";
    } catch (e) {
        alert("Camera error: " + e.message);
    }
});

captureBtn.addEventListener("click", () => {
    if (!cameraStream) return;
    const canvas = document.createElement('canvas');
    canvas.width = cameraPreview.videoWidth;
    canvas.height = cameraPreview.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    capturedImage.src = dataUrl;
    capturedImage.style.display = "block";
    cameraPreview.style.display = "none";

    // Stop camera
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
    cameraBtn.textContent = "Open Camera";
    captureBtn.style.display = "none";

    addMessage("Photo captured! Send it to the agent by speaking.", "system");

    // Send it to websocket if open
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const base64data = dataUrl.split(',')[1];
        websocket.send(JSON.stringify({
            "type": "image",
            "data": base64data,
            "mimeType": "image/jpeg"
        }));
        addMessage("Image sent to agent.", "user");
    } else {
        addMessage("Please start the microphone first to send the image.", "system");
    }
});
