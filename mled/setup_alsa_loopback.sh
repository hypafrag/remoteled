#!/bin/bash
"""
ALSA Loopback Setup Script
Helps configure ALSA loopback for system audio monitoring.
"""

echo "ALSA System Audio Monitoring Setup"
echo "=================================="
echo

# Check if running as root for modprobe
if [[ $EUID -eq 0 ]]; then
    echo "Setting up ALSA loopback module..."
    
    # Load the loopback module
    modprobe snd-aloop
    
    if [ $? -eq 0 ]; then
        echo "✓ ALSA loopback module loaded successfully"
        
        # Make it persistent across reboots
        if ! grep -q "snd-aloop" /etc/modules; then
            echo "snd-aloop" >> /etc/modules
            echo "✓ Added snd-aloop to /etc/modules for persistence"
        fi
        
    else
        echo "✗ Failed to load ALSA loopback module"
        exit 1
    fi
else
    echo "This script needs to be run as root to load kernel modules."
    echo "Please run: sudo $0"
    echo
    echo "Alternatively, you can manually run:"
    echo "  sudo modprobe snd-aloop"
    echo "  echo 'snd-aloop' | sudo tee -a /etc/modules"
    exit 1
fi

echo
echo "Setup complete! You can now:"
echo "1. Check available devices: python3 check_alsa_devices.py"
echo "2. Run the LED controller: python3 mled.py"
echo
echo "The loopback device creates a virtual audio cable where:"
echo "- Applications can play audio to hw:Loopback,0,0"
echo "- Your script can record from hw:Loopback,1,0"
echo
echo "To route system audio through the loopback:"
echo "1. Set system default output to the loopback device"
echo "2. Or use PulseAudio/ALSA configuration to duplicate audio"