// Audio processor worklet for capturing and sending audio
class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 2048;
        this._bytesWritten = 0;
        this._buffer = new Float32Array(this.bufferSize);
    }
    
    initBuffer() {
        this._bytesWritten = 0;
    }

    isBufferEmpty() {
        return this._bytesWritten === 0;
    }

    isBufferFull() {
        return this._bytesWritten === this.bufferSize;
    }

    flush() {
        // Always send the buffer so the server's VAD can detect silence
        const outputBuffer = new Float32Array(this._bytesWritten);
        for (let i = 0; i < this._bytesWritten; i++) {
            outputBuffer[i] = this._buffer[i];
        }
        this.port.postMessage(outputBuffer);
        
        this.initBuffer();
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0];
            for (let i = 0; i < channelData.length; i++) {
                this._buffer[this._bytesWritten++] = channelData[i];
                if (this.isBufferFull()) {
                    this.flush();
                }
            }
        }
        return true;
    }
}

registerProcessor("audio-processor", AudioProcessor);
