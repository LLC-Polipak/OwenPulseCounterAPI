import dataclasses
import logging
from datetime import datetime
from serial import Serial

from app import settings
from app.api.common import SensorReading
from app.owen_counter.owen_ci8 import OwenCI8

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ProbeResult:
    addr: int
    value: float | None
    measured_at: datetime | None
    status: str


class SensorProbeService:
    """
    Сервис для ЧЕСТНОГО одноразового опроса устройства
    """
    
    ADDR_LEN = 8
    PARAMETER_HASH = b"\xC1\x73"
    DEVICE_CLS = OwenCI8
    
    @classmethod
    def probe(cls, *, addr: int) -> ProbeResult:
        if not settings.serial_settings:
            raise RuntimeError("Serial settings not configured")
        
        serial = Serial(**settings.serial_settings)
        serial.close()
        serial.open()
        
        try:
            device = cls.DEVICE_CLS(addr=addr, addr_len=cls.ADDR_LEN)
            
            reading = SensorReading()
            
            try:
                reading.value = device.read_parameter(
                    serial,
                    cls.PARAMETER_HASH,
                )
                reading.time = datetime.now()
                
                status = "OK" if reading.value is not None else "OFFLINE"
            
            except TimeoutError:
                logger.error(f"Sensor {addr} timeout")
                return ProbeResult(
                    addr=addr,
                    value=None,
                    measured_at=None,
                    status="TIMEOUT",
                )
            
            return ProbeResult(
                addr=addr,
                value=reading.value,
                measured_at=reading.time,
                status=status,
            )
        
        finally:
            try:
                serial.close()
            except Exception:
                pass
