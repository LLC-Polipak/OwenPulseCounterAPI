import logging
import random
import struct

from serial import SerialException

from app.providers.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class MockDataProvider(BaseDataProvider):
    """
    «Умная» заглушка для тестирования без физического оборудования.
    Автоматически распознает запросы Modbus RTU и ОВЕН, генерирует реалистичные
    ответы и имитирует флуктуации физических величин.
    """

    def __init__(self, fail_rate: float = 0.05):
        """
        :param fail_rate: Вероятность (0.0 - 1.0) того, что мок сымитирует обрыв
                          или порчу пакета для проверки отказоустойчивости поллера.
        """
        self._is_open = False
        self.fail_rate = fail_rate
        self._response_buffer = b''

        self._ci8_counter = 100500  # Имитация наработанных импульсов
        self._pvt_temp = 24.0  # Базовая температура
        self._pvt_hum = 45.0  # Базовая влажность

    @property
    def name(self) -> str:
        return 'Smart-Mock-485'

    def connect(self) -> bool:
        self._is_open = True
        return True

    def disconnect(self) -> None:
        self._is_open = False

    @property
    def is_connected(self) -> bool:
        return self._is_open

    def clear_buffers(self) -> None:
        self._response_buffer = b''

    def write(self, data: bytes) -> None:
        if not self._is_open:
            raise SerialException('Попытка записи в закрытый Mock-порт')

        if random.random() < self.fail_rate:
            logger.debug('[MOCK] Генерирую случайный сбой (нет ответа).')
            self._response_buffer = b''
            return

        if data.startswith(b'#') and data.endswith(b'\r'):
            self._response_buffer = self._handle_owen_protocol(data)

        elif len(data) == 8 and data[1] == 0x03:
            self._response_buffer = self._handle_modbus_protocol(data)

        else:
            self._response_buffer = b''

    def read(self, size: int) -> bytes:
        if not self._is_open:
            raise SerialException('Попытка чтения из закрытого Mock-порта')

        chunk = self._response_buffer[:size]
        self._response_buffer = self._response_buffer[size:]
        return chunk

    def _handle_modbus_protocol(self, req: bytes) -> bytes:
        addr = req[0]
        reg_addr = struct.unpack('>H', req[2:4])[0]

        if reg_addr == 2250:
            self._pvt_temp += random.uniform(-0.2, 0.2)
            val = self._pvt_temp
        elif reg_addr == 2200:
            self._pvt_hum += random.uniform(-0.5, 0.5)
            self._pvt_hum = max(0.0, min(100.0, self._pvt_hum))
            val = self._pvt_hum
        else:
            return b''

        raw_float = struct.pack('>f', val)
        cdab_float = raw_float[2:4] + raw_float[0:2]

        resp_no_crc = struct.pack('>BBB', addr, 3, 4) + cdab_float
        crc = self._calc_modbus_crc(resp_no_crc)

        return resp_no_crc + struct.pack('<H', crc)

    def _calc_modbus_crc(self, data: bytes) -> int:
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def _handle_owen_protocol(self, ascii_req: bytes) -> bytes:
        bin_req = self._owen_ascii_to_bin(ascii_req)
        if len(bin_req) < 6:
            return b''

        addr_hash = bytearray(bin_req[:4])
        addr_hash[1] &= 0xEF

        self._ci8_counter += random.randint(20, 50)

        data_block = self._int_to_bcd(self._ci8_counter, length_bytes=4)

        resp_bin = addr_hash + data_block
        resp_bin += struct.pack('>H', self._calc_owen_crc(resp_bin))

        return self._owen_bin_to_ascii(resp_bin)

    def _int_to_bcd(self, val: int, length_bytes: int = 4) -> bytes:
        """Переводит целое число в формат BCD (например 1234 -> b'\\x12\\x34')"""
        s = str(val).zfill(length_bytes * 2)
        return bytes(int(s[i : i + 2], 16) for i in range(0, len(s), 2))

    def _calc_owen_crc(self, data: bytes) -> int:
        crc = 0x00
        for byte in data:
            for _ in range(8):
                if (byte ^ (crc >> 8)) & 0x80:
                    crc <<= 1
                    crc ^= 0x8F57
                else:
                    crc <<= 1
                byte <<= 1
                byte &= 0xFF
                crc &= 0xFFFF
        return crc

    def _owen_ascii_to_bin(self, ascii_data: bytes) -> bytes:
        bin_packet = bytearray()
        for i in range(1, len(ascii_data) - 1, 2):
            h_nibble = ascii_data[i] - 0x47
            l_nibble = ascii_data[i + 1] - 0x47
            bin_packet.append((h_nibble << 4) | l_nibble)
        return bytes(bin_packet)

    def _owen_bin_to_ascii(self, bin_data: bytes) -> bytes:
        ascii_packet = bytearray(b'#')
        for byte in bin_data:
            ascii_packet.append(((byte & 0xF0) >> 4) + 0x47)
            ascii_packet.append((byte & 0x0F) + 0x47)
        ascii_packet.append(ord('\r'))
        return bytes(ascii_packet)
