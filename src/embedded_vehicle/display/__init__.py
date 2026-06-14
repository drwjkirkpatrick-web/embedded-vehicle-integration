"""
embedded_vehicle/display/__init__.py
────────────────────────────
Display subsystem for aftermarket Android head-unit integration.

Primary target: JoyBring / similar Android AV touchscreen head units
that expose HDMI input + USB touch back-channel.

Architecture:
- Pi renders the dashboard GUI (Kivy / OpenGL ES)
- HDMI output goes to head-unit HDMI input
- Touch events come back via USB-OTG or I2C touch controller
- Audio routes through Pi DAC → head-unit AUX or HDMI audio
- CAN bus (if head-unit exposes it) bridges to JoyBring radio / amp
"""

from __future__ import annotations

# Lazy imports to avoid dependency errors when display is not configured
# from embedded_vehicle.display.joybring import JoyBringController
# from embedded_vehicle.display.dashboard import Dashboard
# from embedded_vehicle.display.radio import RadioTuner

__all__ = ["JoyBringController", "Dashboard", "RadioTuner"]
