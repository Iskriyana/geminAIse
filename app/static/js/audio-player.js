/**
 * Audio Player Worklet
 */

export async function startAudioPlayerWorklet() {
    // 1. Create an AudioContext
    const audioContext = new AudioContext({
        sampleRate: 24000
    });
    
    
    // 2. Load your custom processor code
    // Add cache buster to ensure we get the latest version
    const workletURL = new URL('./pcm-player-processor.js?v=' + new Date().getTime(), import.meta.url);
    await audioContext.audioWorklet.addModule(workletURL);
    
    // 3. Create an AudioWorkletNode   
    const audioPlayerNode = new AudioWorkletNode(audioContext, 'pcm-player-processor');

    // 4. Connect to the destination
    audioPlayerNode.connect(audioContext.destination);

    // The audioPlayerNode.port is how we send messages (audio data) to the processor
    return [audioPlayerNode, audioContext];
}
