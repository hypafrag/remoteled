#!/usr/bin/env python3
"""
Uses ALSA loopback directly via arecord subprocess - no PortAudio dependency.

Requires Python 3.7 or later.

Usage:
  python3 mled.py <websocket_uri_or_serial_port>

Examples:
  python3 mled.py ws://192.168.3.6:8888        # WebSocket mode (sends Lua code)
  python3 mled.py /dev/ttyUSB0                  # Serial port mode (sends raw RGB data)
  python3 mled.py /dev/ttyACM0                  # Serial port mode (Arduino)

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

Output formats:
- WebSocket: Sends Lua code with LED array to luasand server
- Serial: Sends raw 900 bytes (300 RGB values) directly to serial device
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
import subprocess
import os
import sys
import argparse
from typing import Optional, Tuple

# Configuration constants
AUDIO_UPDATE_INTERVAL_MS = 30  # Audio analysis interval in milliseconds
MAX_COLOR_INTENSITY = 0xAA  # Maximum LED color intensity (170 in decimal)

# ALSA configuration
ALSA_DEVICE = "hw:1,1"  # ALSA loopback capture device (hw:1,1 for loopback)
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_FORMAT = "S32_LE"  # 32-bit little endian (loopback device requirement)
CHUNK_SIZE = 1024

# Frequency band definitions for bass, mid, treble (in Hz)
BASS_FREQ_RANGE = (10, 100)    # Bass frequencies
MID_FREQ_RANGE = (250, 2000)   # Mid frequencies  
TREBLE_FREQ_RANGE = (4000, 20000)  # Treble frequencies

# Default boost factors (used when adaptive boost is disabled)
DEFAULT_BASS_BOOST = 0.6
DEFAULT_MID_BOOST = 1.5
DEFAULT_TREBLE_BOOST = 8.0

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


def generate_led_data(bass: float, mid: float, treble: float, pix_num: int = 300, 
                     enable_bass: bool = True, enable_mid: bool = True, enable_treble: bool = True,
                     center_shift: int = 0, rms_scale: float = 1.0) -> bytes:
    """
    Generate LED data as raw bytes for serial port or Lua code for WebSocket.
    Each frequency range creates its own colored line with quadratic decay from center.
    
    Args:
        bass: Bass level (0.0-1.0) -> Red line length from center
        mid: Mid level (0.0-1.0) -> Green line length from center
        treble: Treble level (0.0-1.0) -> Blue line length from center
        pix_num: Number of LEDs in the strip
        enable_bass: Enable bass frequency visualization (red)
        enable_mid: Enable mid frequency visualization (green)
        enable_treble: Enable treble frequency visualization (blue)
        center_shift: Offset from strip center (-150 to +150 for 300 LED strip)
        rms_scale: Scale factor based on signal RMS (0.0-1.0, quiet=smaller lines)
        
    Returns:
        bytes: Raw RGB data (3 bytes per LED: R, G, B)
    """
    # Clamp values to 0.0-1.0 range
    bass = max(0.0, min(1.0, bass))
    mid = max(0.0, min(1.0, mid))
    treble = max(0.0, min(1.0, treble))
    
    # Calculate center with shift and maximum reach from center
    base_center = pix_num // 2
    center = base_center + center_shift
    
    # Clamp center to valid range
    center = max(0, min(pix_num - 1, center))
    
    # Calculate maximum reach from shifted center (can reach to either edge)
    max_reach_left = center
    max_reach_right = pix_num - 1 - center
    max_reach = max(max_reach_left, max_reach_right)
    
    # Calculate how many LEDs to light up from center for each frequency
    # Apply RMS scaling to make lines smaller on quiet audio
    # Only calculate reach for enabled frequency bands
    bass_reach = int(bass * max_reach * rms_scale) if enable_bass else 0
    mid_reach = int(mid * max_reach * rms_scale) if enable_mid else 0
    treble_reach = int(treble * max_reach * rms_scale) if enable_treble else 0
    
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
            if enable_bass and i <= bass_reach:
                leds[idx] = calculate_intensity(i, bass_reach)      # R (bass)
            if enable_mid and i <= mid_reach:
                leds[idx + 1] = calculate_intensity(i, mid_reach)  # G (mid)
            if enable_treble and i <= treble_reach:
                leds[idx + 2] = calculate_intensity(i, treble_reach)  # B (treble)
                
        # Light up to the left of center
        if center - i >= 0:
            idx = (center - i) * 3
            if enable_bass and i <= bass_reach:
                leds[idx] = calculate_intensity(i, bass_reach)      # R (bass)
            if enable_mid and i <= mid_reach:
                leds[idx + 1] = calculate_intensity(i, mid_reach)  # G (mid)
            if enable_treble and i <= treble_reach:
                leds[idx + 2] = calculate_intensity(i, treble_reach)  # B (treble)
    
    # Handle center LED - full intensity for any active frequency
    if bass_reach > 0 or mid_reach > 0 or treble_reach > 0:
        idx = center * 3
        if enable_bass and bass_reach > 0:
            leds[idx] = MAX_COLOR_INTENSITY      # R (bass)
        if enable_mid and mid_reach > 0:
            leds[idx + 1] = MAX_COLOR_INTENSITY  # G (mid)
        if enable_treble and treble_reach > 0:
            leds[idx + 2] = MAX_COLOR_INTENSITY  # B (treble)
    
    # Return as raw bytes for serial port
    return bytes(leds)

def generate_lua_code(bass: float, mid: float, treble: float, pix_num: int = 300,
                     enable_bass: bool = True, enable_mid: bool = True, enable_treble: bool = True,
                     center_shift: int = 0, rms_scale: float = 1.0) -> str:
    """
    Generate Lua code for WebSocket mode.
    Wrapper around generate_led_data that formats as Lua code.
    """
    led_data = generate_led_data(bass, mid, treble, pix_num, enable_bass, enable_mid, enable_treble, center_shift, rms_scale)
    led_values = ",".join(map(str, led_data))
    return f"return {{{led_values}}}"


class ALSAAudioMonitor:
    """Monitors ALSA audio using arecord subprocess."""
    
    def __init__(self, device: str = ALSA_DEVICE, sample_rate: int = SAMPLE_RATE, adaptive_boost: bool = False,
                 enable_bass: bool = True, enable_mid: bool = True, enable_treble: bool = True, 
                 update_interval_ms: int = AUDIO_UPDATE_INTERVAL_MS, center_shift: int = 0, rms_scale_enabled: bool = False):
        self.device = device
        self.sample_rate = sample_rate
        self.adaptive_boost = adaptive_boost
        self.enable_bass = enable_bass
        self.enable_mid = enable_mid
        self.enable_treble = enable_treble
        self.update_interval_ms = update_interval_ms
        self.center_shift = center_shift
        self.rms_scale_enabled = rms_scale_enabled
        self.audio_queue = queue.Queue()
        self.running = False
        self.process = None
        
        # Auto-adjusting boost factors (only used if adaptive_boost is True)
        self.bass_history = []
        self.mid_history = []
        self.treble_history = []
        self.rms_history = []  # Track RMS levels for line scaling
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
        if not self.adaptive_boost:
            # Use fixed boost factors from global constants
            return DEFAULT_BASS_BOOST, DEFAULT_MID_BOOST, DEFAULT_TREBLE_BOOST
        
        # Add current raw values to history for adaptive boost
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
        bass_boost = max(0.5, min(10.0, bass_boost))
        mid_boost = max(0.5, min(10.0, mid_boost))
        treble_boost = max(0.5, min(10.0, treble_boost))
        
        return bass_boost, mid_boost, treble_boost
    
    def _get_rms_scale_factor(self, rms_level: float) -> float:
        """
        Calculate RMS-based line scaling factor.
        
        Returns a scale factor (0.0-1.0) where:
        - High RMS (loud audio) -> scale factor closer to 1.0 (full length lines)
        - Low RMS (quiet audio) -> scale factor closer to 0.0 (short lines)
        
        This creates natural visual dynamics where quiet audio produces subtle
        visualization and loud audio produces dramatic visualization.
        """
        # Add current RMS to history
        self.rms_history.append(rms_level)
        
        # Keep only recent history
        if len(self.rms_history) > self.history_size:
            self.rms_history.pop(0)
        
        # Calculate average RMS over recent history for stability
        rms_avg = np.mean(self.rms_history) if self.rms_history else 0.001
        
        # Scale RMS to 0.0-1.0 range
        # Typical RMS values range from ~0.001 (very quiet) to ~0.3 (very loud)
        rms_scale = min(1.0, rms_avg / 0.15)  # 0.15 as "full scale" RMS level
        
        # Apply a curve to make the scaling more natural
        # Square root gives more gradual scaling for quiet sounds
        rms_scale = np.sqrt(rms_scale)
        
        # Ensure minimum scale factor so visualization doesn't completely disappear
        rms_scale = max(0.1, rms_scale)
        
        return rms_scale
        
    def _calculate_frequency_loop(self):
        """Analyze frequency bands at configured interval."""
        buffer = []
        samples_per_interval = int(self.sample_rate * (self.update_interval_ms / 1000.0))
        
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
                    
                    # Calculate RMS level for line scaling if enabled
                    if self.rms_scale_enabled:
                        rms_level = np.sqrt(np.mean(samples ** 2))
                        rms_scale = self._get_rms_scale_factor(rms_level)
                    else:
                        rms_scale = 1.0  # No scaling when disabled
                    
                    # First pass: get raw levels for adaptation
                    bass_raw, mid_raw, treble_raw = analyze_frequency_bands(samples, self.sample_rate, (1.0, 1.0, 1.0))
                    
                    # Get adaptive boost factors based on recent history
                    boost_factors = self._get_adaptive_boost_factors(bass_raw, mid_raw, treble_raw)
                    
                    # Second pass: apply adaptive boost factors
                    bass, mid, treble = analyze_frequency_bands(samples, self.sample_rate, boost_factors)
                    
                    # Put frequency analysis and RMS scale in queue for output clients
                    if hasattr(self, 'websocket_queue'):
                        self.websocket_queue.put((bass, mid, treble, rms_scale))
                        
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in frequency analysis: {e}")
                

class SerialPortClient:
    """Serial port client for sending raw LED data."""
    
    def __init__(self, port_path: str, baud_rate: int = 115200):
        self.port_path = port_path
        self.baud_rate = baud_rate
        self.serial_fd = None
        
    def connect_and_send(self, audio_monitor: ALSAAudioMonitor):
        """Connect to serial port and send LED data based on frequency analysis."""
        try:
            # Open serial port using Linux file I/O
            self.serial_fd = os.open(self.port_path, os.O_RDWR | os.O_NOCTTY)
            
            # Configure serial port (similar to main.cpp termios setup)
            try:
                import termios
                
                # Get current attributes
                attrs = termios.tcgetattr(self.serial_fd)
                
                # Configure like main.cpp:
                # 8 data bits, no parity, 1 stop bit, 115200 baud
                attrs[0] = 0  # input flags
                attrs[1] = 0  # output flags  
                attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # control flags
                attrs[3] = 0  # local flags
                attrs[4] = termios.B115200  # input speed
                attrs[5] = termios.B115200  # output speed
                
                # Non-blocking mode
                attrs[6][termios.VTIME] = 0
                attrs[6][termios.VMIN] = 0
                
                # Apply settings
                termios.tcsetattr(self.serial_fd, termios.TCSANOW, attrs)
                termios.tcflush(self.serial_fd, termios.TCIOFLUSH)
                
                print(f"✓ Serial port configured: {self.port_path} @ {self.baud_rate} baud")
                
            except ImportError:
                print(f"⚠️ termios not available, using basic configuration for {self.port_path}")
            except Exception as e:
                print(f"⚠️ Could not configure serial port: {e}")
                print(f"Using basic configuration for {self.port_path}")
            
            # Create queue for frequency analysis values
            audio_monitor.websocket_queue = queue.Queue()
            
            while True:
                try:
                    # Get frequency analysis and RMS scale (non-blocking with timeout)
                    bass, mid, treble, rms_scale = audio_monitor.websocket_queue.get(timeout=0.1)
                    
                    # Generate raw LED data with RMS scaling
                    led_data = generate_led_data(bass, mid, treble, 300, 
                                               audio_monitor.enable_bass, 
                                               audio_monitor.enable_mid, 
                                               audio_monitor.enable_treble,
                                               audio_monitor.center_shift,
                                               rms_scale)
                    
                    # Send raw bytes to serial port (900 bytes total)
                    if len(led_data) == 900:  # 300 LEDs * 3 bytes each
                        bytes_written = os.write(self.serial_fd, led_data)
                        if bytes_written != 900:
                            print(f"⚠️ Only wrote {bytes_written} of 900 bytes")
                    else:
                        print(f"❌ Invalid LED data size: {len(led_data)} (expected 900)")
                        
                except queue.Empty:
                    continue
                    
                except KeyboardInterrupt:
                    print("\nSerial client shutting down...")
                    break
                    
        except Exception as e:
            print(f"Serial port error: {e}")
        finally:
            if self.serial_fd is not None:
                os.close(self.serial_fd)


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
                        # Get frequency analysis and RMS scale (non-blocking with timeout)
                        bass, mid, treble, rms_scale = audio_monitor.websocket_queue.get(timeout=0.1)
                        
                        # Generate Lua code based on frequency analysis with RMS scaling
                        lua_code = generate_lua_code(bass, mid, treble, 300,
                                                    audio_monitor.enable_bass,
                                                    audio_monitor.enable_mid,
                                                    audio_monitor.enable_treble,
                                                    audio_monitor.center_shift,
                                                    rms_scale)
                        
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


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Real-time ALSA audio monitoring with WebSocket or Serial Port output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ws://192.168.3.6:8888              # WebSocket mode (all frequencies)
  %(prog)s /dev/ttyUSB0                        # Serial port mode (all frequencies)
  %(prog)s /dev/ttyACM0 --adaptive-boost      # Serial mode with adaptive boost
  %(prog)s ws://example.com:8888 -a           # WebSocket mode with adaptive boost
  %(prog)s /dev/ttyUSB0 --disable-mid         # Only bass (red) and treble (blue)
  %(prog)s /dev/ttyUSB0 --disable-bass --disable-treble  # Only mid frequencies (green)
  %(prog)s ws://192.168.3.6:8888 --disable-treble        # Only bass (red) and mid (green)
  %(prog)s /dev/ttyUSB0 -i 50                 # 50ms update interval (slower)
  %(prog)s ws://192.168.3.6:8888 --interval 20          # 20ms update interval (faster)
  %(prog)s /dev/ttyUSB0 -c 50                 # Shift center point 50 LEDs to the right
  %(prog)s ws://192.168.3.6:8888 --center-shift -30     # Shift center 30 LEDs to the left
  %(prog)s /dev/ttyUSB0 --rms-scale           # Enable RMS scaling (dynamic line length)
  %(prog)s ws://192.168.3.6:8888 --rms-scale --adaptive-boost  # Full dynamic mode

ALSA Setup:
  1. Load loopback module: sudo modprobe snd-aloop
  2. Set system output to hw:1,0, script monitors hw:1,1
  3. Check devices: arecord -l

Output formats:
  WebSocket: Sends Lua code with LED array to luasand server
  Serial:    Sends raw 900 bytes (300 RGB values) directly to device
        """
    )
    
    parser.add_argument(
        'output',
        help='WebSocket URI (ws://...) or serial port path (/dev/ttyUSB0, etc.)'
    )
    
    parser.add_argument(
        '-a', '--adaptive-boost',
        action='store_true',
        help=f'Enable adaptive boost factors (default: use fixed values {DEFAULT_BASS_BOOST}, {DEFAULT_MID_BOOST}, {DEFAULT_TREBLE_BOOST})'
    )
    
    parser.add_argument(
        '-d', '--device',
        default=ALSA_DEVICE,
        help=f'ALSA capture device (default: {ALSA_DEVICE})'
    )
    
    parser.add_argument(
        '-r', '--sample-rate',
        type=int,
        default=SAMPLE_RATE,
        help=f'Audio sample rate in Hz (default: {SAMPLE_RATE})'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=AUDIO_UPDATE_INTERVAL_MS,
        help=f'Audio analysis update interval in milliseconds (default: {AUDIO_UPDATE_INTERVAL_MS})'
    )
    
    # Frequency band selection options
    parser.add_argument(
        '--enable-bass',
        action='store_true',
        default=True,
        help='Enable bass frequencies (red color, 20-250 Hz) - default: enabled'
    )
    
    parser.add_argument(
        '--disable-bass',
        action='store_true',
        help='Disable bass frequencies (red color)'
    )
    
    parser.add_argument(
        '--enable-mid',
        action='store_true', 
        default=True,
        help='Enable mid frequencies (green color, 250-3000 Hz) - default: enabled'
    )
    
    parser.add_argument(
        '--disable-mid',
        action='store_true',
        help='Disable mid frequencies (green color)'
    )
    
    parser.add_argument(
        '--enable-treble',
        action='store_true',
        default=True,
        help='Enable treble frequencies (blue color, 3000-20000 Hz) - default: enabled'
    )
    
    parser.add_argument(
        '--disable-treble',
        action='store_true',
        help='Disable treble frequencies (blue color)'
    )
    
    parser.add_argument(
        '-c', '--center-shift',
        type=int,
        default=0,
        help='Shift center point by N LEDs (-150 to +150 for 300 LED strip, default: 0)'
    )
    
    parser.add_argument(
        '--rms-scale',
        action='store_true',
        help='Enable RMS-based line scaling (quiet audio = shorter lines, loud audio = longer lines)'
    )
    
    return parser.parse_args()

async def main():
    """Main function to run the audio monitor and output client."""
    args = parse_arguments()
    
    # Handle frequency band enable/disable logic
    enable_bass = not args.disable_bass if args.disable_bass else args.enable_bass
    enable_mid = not args.disable_mid if args.disable_mid else args.enable_mid  
    enable_treble = not args.disable_treble if args.disable_treble else args.enable_treble
    
    # Check if at least one frequency band is enabled
    if not (enable_bass or enable_mid or enable_treble):
        print("❌ Error: At least one frequency band must be enabled!")
        print("Use --enable-bass, --enable-mid, or --enable-treble")
        sys.exit(1)
    
    # Initialize ALSA audio monitor with parsed arguments
    audio_monitor = ALSAAudioMonitor(
        device=args.device,
        sample_rate=args.sample_rate,
        adaptive_boost=args.adaptive_boost,
        enable_bass=enable_bass,
        enable_mid=enable_mid,
        enable_treble=enable_treble,
        update_interval_ms=args.interval,
        center_shift=args.center_shift,
        rms_scale_enabled=args.rms_scale
    )
    
    print(f"Audio device: {args.device}")
    print(f"Sample rate: {args.sample_rate} Hz")
    print(f"Update interval: {args.interval} ms")
    print(f"Center shift: {args.center_shift} LEDs")
    print(f"Adaptive boost: {'enabled' if args.adaptive_boost else 'disabled'}")
    print(f"RMS scaling: {'enabled' if args.rms_scale else 'disabled'}")
    if not args.adaptive_boost:
        print(f"Fixed boost factors: bass={DEFAULT_BASS_BOOST}, mid={DEFAULT_MID_BOOST}, treble={DEFAULT_TREBLE_BOOST}")
    if args.rms_scale:
        print("RMS scaling: quiet audio = shorter lines, loud audio = longer lines")
    
    # Display enabled frequency bands
    bands = []
    if enable_bass:
        bands.append("bass (red, 20-250 Hz)")
    if enable_mid:
        bands.append("mid (green, 250-3000 Hz)")
    if enable_treble:
        bands.append("treble (blue, 3000-20000 Hz)")
    print(f"Enabled frequency bands: {', '.join(bands)}")
    print()
    
    try:
        print("Starting audio monitoring...")
        audio_monitor.start_monitoring()
        
        # Detect if target is WebSocket URL or serial port
        if args.output.startswith("ws://") or args.output.startswith("wss://"):
            print(f"WebSocket mode: connecting to {args.output}")
            ws_client = WebSocketClient(args.output, "code")
            await ws_client.connect_and_send(audio_monitor)
        else:
            print(f"Serial port mode: using {args.output}")
            serial_client = SerialPortClient(args.output)
            # Serial client runs synchronously, so we need to run it in a thread
            import threading
            
            def run_serial_client():
                serial_client.connect_and_send(audio_monitor)
            
            serial_thread = threading.Thread(target=run_serial_client)
            serial_thread.daemon = True
            serial_thread.start()
            
            # Keep the main thread alive
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
        
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
