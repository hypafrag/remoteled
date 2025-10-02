#!/usr/bin/env python3
"""
Real-time microphone RMS monitoring with WebSocket client.
Connects to WebSocket server and sends Lua code based on RMS values.
"""

import asyncio
import websockets
import sounddevice as sd
import numpy as np
import threading
import queue
import time
from typing import Optional, Tuple

# Configuration constants
AUDIO_UPDATE_INTERVAL_MS = 40  # Audio analysis interval in milliseconds
USE_SYSTEM_AUDIO = False  # True for system playback, False for microphone input
MAX_COLOR_INTENSITY = 0xAA  # Maximum LED color intensity (170 in decimal)

# Frequency band definitions for bass, mid, treble (in Hz)
BASS_FREQ_RANGE = (20, 250)    # Bass frequencies
MID_FREQ_RANGE = (250, 3000)   # Mid frequencies  
TREBLE_FREQ_RANGE = (3000, 20000)  # Treble frequencies

AUTO_ADJUST_BOOST = False  # Enable auto-adjusting boost factors

def analyze_frequency_bands(audio_data: np.ndarray, sample_rate: int, boost_factors: Tuple[float, float, float] = (3.0, 2.0, 4.0)) -> Tuple[float, float, float]:
    """
    Analyze audio data and extract bass, mid, and treble levels.
    
    Args:
        audio_data: Audio samples
        sample_rate: Sample rate in Hz
        boost_factors: Tuple of (bass_boost, mid_boost, treble_boost) multipliers
        
    Returns:
        Tuple of (bass, mid, treble) levels normalized to 0.0-1.0
    """
    # Apply window function to reduce spectral leakage
    windowed = audio_data * np.hanning(len(audio_data))
    
    # Compute FFT
    fft = np.fft.fft(windowed)
    freqs = np.fft.fftfreq(len(fft), 1/sample_rate)
    
    # Take only positive frequencies and their magnitudes
    magnitude = np.abs(fft[:len(fft)//2])
    freqs = freqs[:len(freqs)//2]
    
    # Extract frequency bands
    bass_mask = (freqs >= BASS_FREQ_RANGE[0]) & (freqs <= BASS_FREQ_RANGE[1])
    mid_mask = (freqs >= MID_FREQ_RANGE[0]) & (freqs <= MID_FREQ_RANGE[1])
    treble_mask = (freqs >= TREBLE_FREQ_RANGE[0]) & (freqs <= TREBLE_FREQ_RANGE[1])
    
    # Calculate average magnitude for each band
    bass_level = np.mean(magnitude[bass_mask]) if np.any(bass_mask) else 0.0
    mid_level = np.mean(magnitude[mid_mask]) if np.any(mid_mask) else 0.0
    treble_level = np.mean(magnitude[treble_mask]) if np.any(treble_mask) else 0.0
    
    # Normalize to 0.0-1.0 range with adaptive boost factors
    max_magnitude = np.max(magnitude) if len(magnitude) > 0 else 1.0
    if max_magnitude > 0:
        bass_boost, mid_boost, treble_boost = boost_factors
        bass_level = min(1.0, bass_level / max_magnitude * bass_boost)
        mid_level = min(1.0, mid_level / max_magnitude * mid_boost)
        treble_level = min(1.0, treble_level / max_magnitude * treble_boost)
    
    return bass_level, mid_level, treble_level


def generate_lua_code(bass: float, mid: float, treble: float, pix_num: int = 300) -> str:
    """
    Generate Lua code with three colored lines extending from center outward.
    Each frequency range creates its own colored line with quadratic decay from center.
    
    Args:
        bass: Bass level (0.0-1.0) -> Red line length from center
        mid: Mid level (0.0-1.0) -> Green line length from center
        treble: Treble level (0.0-1.0) -> Blue line length from center
        pix_num: Number of LEDs in the strip
        
    Returns:
        str: Simple Lua code that returns pre-calculated LED array
    """
    # Clamp values to 0.0-1.0 range
    bass = max(0.0, min(1.0, bass))
    mid = max(0.0, min(1.0, mid))
    treble = max(0.0, min(1.0, treble))
    
    # Calculate center and maximum reach from center
    center = pix_num // 2
    max_reach = center  # Maximum LEDs we can light from center to edge
    
    # Calculate how many LEDs to light up from center for each frequency
    bass_reach = int(bass * max_reach)
    mid_reach = int(mid * max_reach)
    treble_reach = int(treble * max_reach)
    
    # Create RGB byte array (3 bytes per LED: R, G, B)
    leds = []
    
    # Initialize all LEDs to black
    for i in range(pix_num):
        leds.extend([0, 0, 0])  # R, G, B = 0, 0, 0 (black)
    
    def calculate_intensity(distance_from_center: int, max_distance: int) -> int:
        """Calculate LED intensity using quadratic decay from center."""
        if max_distance == 0:
            return 0
        # Quadratic decay: intensity = max * (1 - (distance/max_distance)^2)
        decay_factor = 1.0 - (distance_from_center / max_distance) ** 2
        return int(MAX_COLOR_INTENSITY * decay_factor)
    
    # Light up LEDs from center outward for each frequency band with quadratic decay
    for i in range(1, max(bass_reach, mid_reach, treble_reach) + 1):
        # Light up to the right of center
        if center + i < pix_num:
            idx = (center + i) * 3
            if i <= bass_reach:
                leds[idx] = calculate_intensity(i, bass_reach)      # R (bass)
            if i <= mid_reach:
                leds[idx + 1] = calculate_intensity(i, mid_reach)  # G (mid)
            if i <= treble_reach:
                leds[idx + 2] = calculate_intensity(i, treble_reach)  # B (treble)
                
        # Light up to the left of center
        if center - i >= 0:
            idx = (center - i) * 3
            if i <= bass_reach:
                leds[idx] = calculate_intensity(i, bass_reach)      # R (bass)
            if i <= mid_reach:
                leds[idx + 1] = calculate_intensity(i, mid_reach)  # G (mid)
            if i <= treble_reach:
                leds[idx + 2] = calculate_intensity(i, treble_reach)  # B (treble)
    
    # Handle center LED - full intensity for any active frequency
    if bass_reach > 0 or mid_reach > 0 or treble_reach > 0:
        idx = center * 3
        if bass_reach > 0:
            leds[idx] = MAX_COLOR_INTENSITY      # R (bass)
        if mid_reach > 0:
            leds[idx + 1] = MAX_COLOR_INTENSITY  # G (mid)
        if treble_reach > 0:
            leds[idx + 2] = MAX_COLOR_INTENSITY  # B (treble)
    
    # Generate simple Lua code with pre-calculated values
    led_values = ",".join(map(str, leds))
    lua_code = f"return {{{led_values}}}"
    
    return lua_code


class AudioFrequencyMonitor:
    """Monitors audio input (microphone or system audio) and analyzes frequency bands."""
    
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_queue = queue.Queue()
        self.running = False
        self.stream = None
        
        # Auto-adjusting boost factors
        self.bass_history = []
        self.mid_history = []
        self.treble_history = []
        self.history_size = 100  # Keep last 100 measurements for adaptation
        self.adaptation_rate = 0.05  # How fast to adapt (0.01 = slow, 0.1 = fast)
        
    def start_monitoring(self):
        """Start monitoring audio input (microphone or system audio)."""
        self.running = True
        
        if USE_SYSTEM_AUDIO:
            print("Attempting to monitor system audio playback...")
            try:
                # Try to find a loopback device or use default output for monitoring
                devices = sd.query_devices()
                print("Available audio devices:")
                for i, device in enumerate(devices):
                    print(f"  {i}: {device['name']} ({'input' if device['max_input_channels'] > 0 else 'output'})")
                
                # For system audio, we need a loopback device or virtual audio cable
                # This will likely require BlackHole or similar on macOS
                self.stream = sd.InputStream(
                    channels=2,  # System audio is usually stereo
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    dtype=np.float32,
                    callback=self._audio_callback
                )
                print("✓ System audio monitoring configured")
            except Exception as e:
                print(f"⚠️ Could not configure system audio monitoring: {e}")
                print("Falling back to microphone input...")
                self._setup_microphone()
        else:
            print("Monitoring microphone input...")
            self._setup_microphone()
    
    def _setup_microphone(self):
        """Setup microphone input stream."""
        self.stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            dtype=np.float32,
            callback=self._audio_callback
        )
        
        self.stream.start()
        
        # Start frequency analysis thread
        freq_thread = threading.Thread(target=self._calculate_frequency_loop)
        freq_thread.daemon = True
        freq_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring microphone input."""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
    def _audio_callback(self, in_data, frames, time, status):
        """Callback function for audio stream."""
        if status:
            print(f"Audio callback status: {status}")
        
        # Handle both mono and stereo input
        if len(in_data.shape) > 1 and in_data.shape[1] > 1:
            # Stereo - mix to mono by averaging channels
            audio_data = np.mean(in_data, axis=1)
        else:
            # Mono - take first channel
            audio_data = in_data[:, 0] if len(in_data.shape) > 1 else in_data
            
        self.audio_queue.put(audio_data)
    
    def _get_adaptive_boost_factors(self, bass_raw: float, mid_raw: float, treble_raw: float) -> Tuple[float, float, float]:
        """Calculate adaptive boost factors based on recent audio history."""
        # Add current raw values to history
        self.bass_history.append(bass_raw)
        self.mid_history.append(mid_raw)
        self.treble_history.append(treble_raw)
        
        # Keep only recent history
        if len(self.bass_history) > self.history_size:
            self.bass_history.pop(0)
            self.mid_history.pop(0)
            self.treble_history.pop(0)
        
        # Calculate target level (we want each band to reach ~0.7 on average)
        target_level = 0.7
        
        # Calculate average levels over recent history
        bass_avg = np.mean(self.bass_history) if self.bass_history else 0.001
        mid_avg = np.mean(self.mid_history) if self.mid_history else 0.001
        treble_avg = np.mean(self.treble_history) if self.treble_history else 0.001
        
        # Calculate desired boost factors to reach target
        bass_boost = target_level / max(bass_avg, 0.001)
        mid_boost = target_level / max(mid_avg, 0.001)
        treble_boost = target_level / max(treble_avg, 0.001)
        
        # Clamp boost factors to reasonable range
        if AUTO_ADJUST_BOOST:
            bass_boost = max(0.5, min(10.0, bass_boost))
            mid_boost = max(0.5, min(10.0, mid_boost))
            treble_boost = max(0.5, min(10.0, treble_boost))
        else:
            bass_boost = 0.4
            mid_boost = 0.4
            treble_boost = 10.0
        
        return bass_boost, mid_boost, treble_boost
        
    def _calculate_frequency_loop(self):
        """Analyze frequency bands at configured interval."""
        buffer = []
        samples_per_interval = int(self.sample_rate * (AUDIO_UPDATE_INTERVAL_MS / 1000.0))
        
        while self.running:
            try:
                # Get audio data from queue
                audio_chunk = self.audio_queue.get(timeout=0.1)
                buffer.extend(audio_chunk)
                
                # Analyze frequency bands when we have enough samples
                if len(buffer) >= samples_per_interval:
                    # Take the required samples and keep the rest for next calculation
                    samples = np.array(buffer[:samples_per_interval])
                    buffer = buffer[samples_per_interval:]
                    
                    # First pass: get raw levels for adaptation
                    bass_raw, mid_raw, treble_raw = analyze_frequency_bands(samples, self.sample_rate, (1.0, 1.0, 1.0))
                    
                    # Get adaptive boost factors based on recent history
                    boost_factors = self._get_adaptive_boost_factors(bass_raw, mid_raw, treble_raw)
                    
                    # Second pass: apply adaptive boost factors
                    bass, mid, treble = analyze_frequency_bands(samples, self.sample_rate, boost_factors)
                    
                    # Put frequency analysis in queue for WebSocket sender
                    if hasattr(self, 'websocket_queue'):
                        self.websocket_queue.put((bass, mid, treble))
                        
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in frequency analysis: {e}")
                

class WebSocketClient:
    """WebSocket client for sending Lua code."""
    
    def __init__(self, uri: str, protocol: str = "code"):
        self.uri = uri
        self.protocol = protocol
        self.websocket = None
        
    async def connect_and_send(self, audio_monitor: AudioFrequencyMonitor):
        """Connect to WebSocket and send Lua code based on RMS values."""
        try:
            # Connect to WebSocket with specified protocol
            async with websockets.connect(
                self.uri, 
                subprotocols=[self.protocol]
            ) as websocket:
                self.websocket = websocket
                print(f"Connected to {self.uri} with protocol '{self.protocol}'")
                
                # Create queue for frequency analysis values
                audio_monitor.websocket_queue = queue.Queue()
                
                while True:
                    try:
                        # Get frequency analysis (non-blocking with timeout)
                        bass, mid, treble = audio_monitor.websocket_queue.get(timeout=0.1)
                        
                        # Generate Lua code based on frequency analysis
                        lua_code = generate_lua_code(bass, mid, treble)
                        
                        # Send Lua code if it's not empty
                        if lua_code.strip():
                            await websocket.send(lua_code)
                            # print(f"Sent Lua code (RMS: {rms:.4f})")
                            
                            # Wait for response
                            try:
                                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                if response == "Accepted":
                                    # print("✓ Code accepted")
                                    pass
                                else:
                                    print(f"❌ Unexpected response: '{response}' - Exiting")
                                    return
                            except asyncio.TimeoutError:
                                print("⚠️ No response received within 1 second")
                        else:
                            # For debugging - show frequency levels even when not sending code
                            print(f"Bass: {bass:.3f}, Mid: {mid:.3f}, Treble: {treble:.3f} (no Lua code generated)")
                            
                    except queue.Empty:
                        # Check if connection is still alive
                        await websocket.ping()
                        continue
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket connection closed")
                        break
                        
        except Exception as e:
            print(f"WebSocket error: {e}")


async def main():
    """Main function to run the microphone RMS monitor and WebSocket client."""
    # WebSocket configuration
    websocket_uri = "ws://192.168.3.6:8888"
    
    # Initialize audio monitor
    audio_monitor = AudioFrequencyMonitor()
    
    # Initialize WebSocket client
    ws_client = WebSocketClient(websocket_uri, "code")
    
    try:
        print("Starting audio monitoring...")
        audio_monitor.start_monitoring()
        
        print(f"Connecting to WebSocket at {websocket_uri}...")
        await ws_client.connect_and_send(audio_monitor)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        audio_monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
