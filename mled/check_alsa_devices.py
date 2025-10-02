#!/usr/bin/env python3
"""
ALSA Audio Device Checker
Helps identify available ALSA audio devices using command-line tools.
No Python audio library dependencies required.
"""

import sys
import subprocess

def main():
    print("ALSA Audio Device Information")
    print("=" * 50)
    
    # Check if ALSA loopback module is loaded
    print("1. Checking ALSA loopback module status:")
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        if 'snd_aloop' in result.stdout:
            print("✓ ALSA loopback module (snd-aloop) is loaded")
        else:
            print("⚠️  ALSA loopback module not loaded")
            print("   Load with: sudo modprobe snd-aloop")
    except Exception as e:
        print(f"Could not check module status: {e}")
    
    print("\n2. Available ALSA capture devices:")
    print("-" * 30)
    
    # List ALSA capture devices
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
            
            # Check for loopback device
            if 'Loopback' in result.stdout:
                print("✓ Found ALSA Loopback device!")
                print("  - Use hw:1,1 to capture from loopback")
                print("  - Set system output to hw:1,0")
            else:
                print("⚠️  No Loopback device found")
        else:
            print(f"Error listing devices: {result.stderr}")
    except FileNotFoundError:
        print("arecord command not found. Install alsa-utils:")
        print("  sudo apt install alsa-utils")
        return 1
    except Exception as e:
        print(f"Error running arecord: {e}")
    
    print("\n3. Available ALSA playback devices:")
    print("-" * 30)
    
    # List ALSA playback devices
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error listing playback devices: {result.stderr}")
    except Exception as e:
        print(f"Error running aplay: {e}")
    
    print("\n4. Setup Instructions:")
    print("-" * 20)
    print("To use system audio monitoring:")
    print("1. Load loopback module: sudo modprobe snd-aloop")
    print("2. Set system audio output to 'Loopback, Loopback PCM (hw:1,0)'")
    print("3. The script will monitor hw:1,1 (loopback capture)")
    print("4. Test with: arecord -D hw:1,1 -f S16_LE -r 44100 -c 2 -t raw | hexdump -C")
    print("   (Play music and you should see changing data)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())