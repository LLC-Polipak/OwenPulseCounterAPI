from typing import Any

from app.owen_drivers.owen_ci8 import OwenCI8
from app.owen_drivers.modbus_pvt110 import ModbusPVT110

serial_settings: dict[str, Any] = {
    'port': '/dev/ttyUSB0',
    'baudrate': 9600,
    'bytesize': 8,
    'parity': 'N',
    'stopbits': 1,
    'timeout': 1.0
}

sensors_settings = [
    {
        'name': 'dev1_ci8',
        'driver': OwenCI8,
        'addr': 2,
        'addr_len': 8,
        'parameter': OwenCI8.DCNT
    },
    {

        'name': 'dev1_pvt',
        'driver': ModbusPVT110,
        'addr': 16,
        'addr_len': 8,
        'parameter': None
    }
]

POLL_DELAY = 0.5
INTER_SENSOR_DELAY = 0.25
