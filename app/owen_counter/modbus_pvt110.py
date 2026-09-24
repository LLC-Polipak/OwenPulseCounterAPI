import logging
import struct
import time

from serial import Serial

logger = logging.getLogger(__name__)


class ModbusPVT110:
    # Точные регистры из конфигуратора
    T = 2250  # 0x08CA
    H = 2200  # 0x0898

    def __init__(self, addr: int, addr_len: int = 8):
        self.addr = addr

    def _calculate_crc(self, data: bytes) -> int:
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _i in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def _read_register(self, serial_if, register_addr: int):
        """Внутренний метод для чтения одного регистра"""
        request = struct.pack('>BBHH', self.addr, 3, register_addr, 2)
        crc = self._calculate_crc(request)
        request += struct.pack('<H', crc)

        serial_if.reset_input_buffer()
        serial_if.write(request)
        time.sleep(0.1)

        response = serial_if.read(9)

        if len(response) < 9 or response[1] == 0x83:
            return None

        received_crc = struct.unpack('<H', response[-2:])[0]
        if received_crc != self._calculate_crc(response[:-2]):
            return None

        payload = response[3:7]
        value = struct.unpack('>f', payload[2:4] + payload[0:2])[0]
        return round(value, 2)

    def read_parameter(self, serial_if, parameter_hash: any = None):
        """Читает температуру и влажность."""
        try:
            temp = self._read_register(serial_if, 2250)
            if temp is None:
                return None

            hum = self._read_register(serial_if, 2200)
            if hum is None:
                return None

            return {
                "temperature": temp,
                "humidity": hum
            }

        except Exception as e:
            logger.error(f"Modbus Error: {e}")
            return None
