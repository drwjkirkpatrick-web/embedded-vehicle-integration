"""
embedded_vehicle/modern_vehicle/__init__.py
───────────────────────────────────
Modern vehicle adapter for CAN-bus cars (2008+).

Extends the base embedded_vehicle platform to support:
- CAN 2.0B / CAN FD (up to 8 Mbps)
- ISO 15765-4 (OBD-II over CAN)
- UDS (Unified Diagnostic Services) — ECU read/write/flash
- Multiple CAN buses (powertrain, body, chassis, infotainment)
- LIN bus (door modules, seats, sensors)
- Ethernet/DoIP (Diagnostics over IP — modern VW/Audi/BMW)
- TPMS direct (433/315 MHz RF receivers)
- Blind spot radar (24/77 GHz CAN interfaces)
- 360° camera systems (MIPI-CSI2 multiplexers)
- Parking ultrasonic arrays (8-12 sensors)
- Radar fusion (front/rear radar modules)
- Driver monitoring (IR camera + drowsiness AI)
- Ambient interior sensing (CO2, VOC, particulate)

Usage:
    from embedded_vehicle.modern_vehicle import ModernVehicleAdapter
    adapter = ModernVehicleAdapter()
    await adapter.start()
    # Access modern features
    await adapter.read_ecu_identification(0x01)  # ECM
    await adapter.adaptive_cruise_set_speed(65)  # mph
"""

from __future__ import annotations

from embedded_vehicle.modern_vehicle.can_multibus import CANMultibusController
from embedded_vehicle.modern_vehicle.uds_client import UDSClient
from embedded_vehicle.modern_vehicle.tpms_direct import TPMSSensorArray
from embedded_vehicle.modern_vehicle.radar_fusion import RadarFusionProcessor
from embedded_vehicle.modern_vehicle.driver_monitor import DriverMonitor
from embedded_vehicle.modern_vehicle.interior_sensing import InteriorEnvironmentSensor

__all__ = [
    "CANMultibusController",
    "UDSClient",
    "TPMSSensorArray",
    "RadarFusionProcessor",
    "DriverMonitor",
    "InteriorEnvironmentSensor",
]
