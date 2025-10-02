#!/usr/bin/env python3
"""
Real-time ALSA audio monitoring with WebSocket client.
Uses ALSA loopback directly via arecord subprocess - no PortAudio dependency.

Requires Python 3.7 or later.

Setup ALSA loopback for system audio monitoring:
1. Load the ALSA loopback module: sudo modprobe snd-aloop
2. Configure audio to route through loopback:
   - Set system output to "Loopback, Loopback PCM (hw:1,0)"
   - This script monitors "Loopback, Loopback PCM (hw:1,1)"
3. Install alsa-utils: sudo apt install alsa-utils
4. Check devices with: arecord -l

The loopback creates a virtual audio cable where:
- hw:1,0 is the playback side (system audio output)
- hw:1,1 is the capture side (this script input)
"""

import sys

# Check Python version compatibility
if sys.version_info < (3, 7):
    print("This script requires Python 3.7 or later.")
    sys.exit(1)

import asyncio
import websockets
import numpy as np
import threading
import queue
import time
import subprocess
import struct
from typing import Optional, Tuple

# Configuration constants
AUDIO_UPDATE_INTERVAL_MS = 40  # Audio analysis interval in milliseconds
USE_SYSTEM_AUDIO = True  # True for system playback, False for microphone input
MAX_COLOR_INTENSITY = 0xAA  # Maximum LED color intensity (170 in decimal)

# ALSA configuration
ALSA_DEVICE = "hw:1,1"  # ALSA loopback capture device (hw:1,1 for loopback)
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_FORMAT = "S32_LE"  # 32-bit little endian (loopback device requirement)
CHUNK_SIZE = 1024

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


class ALSAAudioMonitor:
    """Monitors ALSA audio using arecord subprocess."""
    
    def __init__(self, device: str = ALSA_DEVICE, sample_rate: int = SAMPLE_RATE):
        self.device = device
        self.sample_rate = sample_rate
        self.audio_queue = queue.Queue()
        self.running = False
        self.process = None
        
        # Auto-adjusting boost factors
        self.bass_history = []
        self.mid_history = []
        self.treble_history = []
        self.history_size = 100
        
    def start_monitoring(self):
        """Start monitoring ALSA system audio."""
        self.running = True
        
        # Check if ALSA loopback module is loaded
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'snd_aloop' not in result.stdout:
                print("⚠️  ALSA loopback module not loaded. Run: sudo modprobe snd-aloop")
        except:
            pass
        
        # List available ALSA devices
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            print("Available ALSA capture devices:")
            print(result.stdout)
        except:
            print("Could not list ALSA devices. Make sure alsa-utils is installed.")
        
        try:
            # Start arecord subprocess to capture audio
            cmd = [
                'arecord',
                '-D', self.device,
                '-f', SAMPLE_FORMAT,
                '-r', str(self.sample_rate),
                '-c', str(CHANNELS),
                '-t', 'raw'
            ]
            
            print(f"Starting ALSA capture: {' '.join(cmd)}")
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Start audio reading thread
            audio_thread = threading.Thread(target=self._read_audio_loop)
            audio_thread.daemon = True
            audio_thread.start()
            
            # Start frequency analysis thread
            freq_thread = threading.Thread(target=self._calculate_frequency_loop)
            freq_thread.daemon = True
            freq_thread.start()
            
            print(f"✓ ALSA audio monitoring started on device {self.device}")
            
        except Exception as e:
            print(f"Failed to start ALSA monitoring: {e}")
            print("\nTroubleshooting:")
            print("1. Check if ALSA loopback is loaded: lsmod | grep snd_aloop")
            print("2. Load loopback module: sudo modprobe snd-aloop")
            print("3. Set system audio output to 'Loopback, Loopback PCM (hw:1,0)'")
            print("4. This script monitors 'hw:1,1' (loopback capture)")
            print("5. Install alsa-utils: sudo apt install alsa-utils")
            
    def stop_monitoring(self):
        """Stop monitoring."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait()
            
    def _read_audio_loop(self):
        """Read audio data from arecord subprocess."""
        bytes_per_sample = 4  # 32-bit = 4 bytes
        bytes_per_frame = bytes_per_sample * CHANNELS
        bytes_per_chunk = CHUNK_SIZE * bytes_per_frame
        
        while self.running and self.process:
            try:
                # Read chunk from subprocess
                data = self.process.stdout.read(bytes_per_chunk)
                if not data:
                    break
                    
                # Convert bytes to numpy array
                # S32_LE = signed 32-bit little endian
                audio_data = np.frombuffer(data, dtype=np.int32)
                
                # Reshape to separate channels and convert to float
                if CHANNELS == 2:
                    audio_data = audio_data.reshape(-1, 2)
                    # Mix stereo to mono
                    audio_data = np.mean(audio_data, axis=1)
                
                # Convert to float in range [-1.0, 1.0]
                # 32-bit signed integer range is -2147483648 to 2147483647
                audio_data = audio_data.astype(np.float32) / 2147483648.0
                
                # Put in queue for frequency analysis
                self.audio_queue.put(audio_data)
                
            except Exception as e:
                print(f"Error reading audio: {e}")
                break
    
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
        
        # Use fixed boost factors for simplicity
        return 2.0, 1.5, 8.0
        
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
        
    async def connect_and_send(self, audio_monitor: ALSAAudioMonitor):
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
    
    # Initialize ALSA audio monitor
    audio_monitor = ALSAAudioMonitor()
    
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
    # Python 3.7 compatible asyncio event loop
    try:
        # Try using asyncio.run() if available (Python 3.7+)
        asyncio.run(main())
    except AttributeError:
        # Fallback for older Python versions
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main())
        finally:
            loop.close()
