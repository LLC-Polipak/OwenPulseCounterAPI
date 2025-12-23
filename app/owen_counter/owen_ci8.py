import logging
from datetime import timedelta
from typing import Any

from serial import Serial

from app.api.config import configure_logging
from app.owen_counter.exeptions import (
    BCDValueError,
    ImproperlyConfiguredError,
    PacketDecodeError,
    PacketFooterError,
    PacketHeaderError,
    PacketLenError,
    TimeValueError,
)

configure_logging()
logger = logging.getLogger(__name__)


class DataConverters:
    __CLK_DATA_LEN = 7
    __CLK_HOURS_BYTES = slice(0, 3)
    __CLK_MINUTES_BYTES = slice(3, 4)
    __CLK_SECONDS_BYTES = slice(4, 5)
    __CLK_HUNDREDTHS_SECOND_BYTES = slice(5, 6)

    @staticmethod
    def bcd_to_int(data: bytes | bytearray) -> int:
        """
        Конвертирует DEC_dot0 (BCD) в int.
        """
        if len(data) == 0:
            raise BCDValueError(data=data)
        result = 0
        for i, byte in enumerate(reversed(data)):
            l_nibble = byte & 0x0F
            h_nibble = byte >> 4
            if l_nibble > 9 or h_nibble > 9:
                raise BCDValueError(data=data)
            result += l_nibble * 10 ** (i * 2)
            result += h_nibble * 10 ** (i * 2 + 1)
        return result

    @classmethod
    def clk_to_timedelta(cls, data: bytes | bytearray) -> timedelta:
        """
        Конвертирует CLK_frm в timedelta.
        """
        if len(data) != cls.__CLK_DATA_LEN:
            raise TimeValueError(data=data)
        hours = cls.bcd_to_int(data[cls.__CLK_HOURS_BYTES])
        minutes = cls.bcd_to_int(data[cls.__CLK_MINUTES_BYTES])
        seconds = cls.bcd_to_int(data[cls.__CLK_SECONDS_BYTES])
        milliseconds = cls.bcd_to_int(data[cls.__CLK_HUNDREDTHS_SECOND_BYTES]) * 10
        return timedelta(
            hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
        )


class OwenCI8:
    # Параметры СИ8
    MAX_VALUE: int = 9_999_999
    
    DCNT: bytes = b'\xc1\x73'  # hash параметра DCNT
    DSPD: bytes = b'\x8f\xc2'  # hash параметра DSPD
    DTMR: bytes = b'\xe6\x9c'  # hash параметра DTMR

    PARAMS: dict[bytes, dict[str, Any]] = {
        DCNT: {'response_len': 22, 'converter': DataConverters.bcd_to_int},
        DSPD: {'response_len': 22, 'converter': DataConverters.bcd_to_int},
        DTMR: {'response_len': 28, 'converter': DataConverters.clk_to_timedelta},
    }

    # Параметры протокола Owen
    __OWEN_ASCII_LOWEST_CODE: int = 0x47  # ASCII код для тетрады 0x0
    __OWEN_ASCII_HIGHEST_CODE: int = 0x56  # ASCII код для тетрады 0xF
    __OWEN_PACKET_HEADER: bytes = b'#'  # маркер начала пакета
    __OWEN_PACKET_FOOTER: bytes = b'\r'  # маркер окончания пакета
    __OWEN_PARAM_HASH_LEN: int = 2  # количество байт хеша параметров
    __OWEN_ADDR_LENS: tuple[int] = (8, 11)  # допустимые длины адресов
    # Поля двоичного пакета Owen
    __OWEN_ADDR_BYTES: slice = slice(0, 2)  # 2-й байт содержит доп. данные
    __OWEN_CRC_BYTES: slice = slice(-2, None)
    __OWEN_CRC_DATA_BYTES: slice = slice(0, -2)
    __OWEN_DATA_BYTES: slice = slice(4, -2)
    __OWEN_HASH_BYTES: slice = slice(2, 4)

    __ADDR_ERR_MSG = (
        'Неверный адрес устройства: {actual}. '
        'Установите значение из диапазона: 0 - {max_addr}'
    )
    __ADDR_LEN_ERR_MSG = (
        'Неверная длина адреса устройства: {actual}. '
        'Установите одно из значений: {expected}.'
    )
    __HASH_ERR_MSG = 'Параметр с хешем {actual} не поддерживается устройством.'
    __HASH_LEN_ERR_MSG = (
        'Неверная длина хеша параметра: {actual}. Ожидалось: {expected}.'
    )
    __RESPONSE_ADDR_ERR_MSG = (
        'Неверный адрес устройства в ответном пакете: {actual}. Ожидалось: {expected}.'
    )
    __RESPONSE_HASH_ERR_MSG = (
        'Неверный hash параметра в ответном пакете: {actual}. Ожидалось: {expected}.'
    )
    __RESPONSE_CRC_ERR_MSG = (
        'Неверный CRC в ответном пакете: {actual}. Ожидалось: {expected}'
    )
    __ZERO_DATA_LEN_ERR_MSG = 'В ответном пакете нет данных.'

    def __init__(self, addr: int, addr_len: int = 8):
        """
        :param addr: адрес счетчика СИ8,
        :param addr_len: длина адреса.
        """
        # проверяем валидность addr_len
        if addr_len not in self.__OWEN_ADDR_LENS:
            raise ImproperlyConfiguredError(
                self.__ADDR_LEN_ERR_MSG.format(
                    actual=addr_len, expected=self.__OWEN_ADDR_LENS
                )
            )
        self.addr_len = addr_len
        # проверяем валидность адреса, разделяем на байты
        max_addr = 2**addr_len - 1
        if not isinstance(addr, int) or not 0 <= addr <= max_addr:
            raise ImproperlyConfiguredError(
                self.__ADDR_ERR_MSG.format(actual=addr, max_addr=max_addr)
            )
        addr <<= 16 - addr_len
        self.addr = addr.to_bytes(2, 'big')

    @staticmethod
    def calc_owen_crc(data: bytes) -> bytes:
        """
        Возвращает ОВЕН CRC16. Полином 0x8F57.
        :param data: Данные.
        :return: CRC.
        """
        crc = 0x00
        for byte in data:
            for _j in range(8):
                if (byte ^ (crc >> 8)) & 0x80:
                    crc <<= 1
                    crc ^= 0x8F57
                else:
                    crc <<= 1
                byte <<= 1
                byte &= 0xFF
                crc &= 0xFFFF
        return crc.to_bytes(2, 'big')

    def get_command_packet(self, parameter_hash: bytes) -> bytearray:
        """
        Подготавливает двоичный пакет запроса парамера.
        Подготовленный пакет содержит поля адреса, признака запроса и CRC.
        :param parameter_hash: Hash запрашиваемого параметра.
        :return: Двоичный пакет.
        """
        hash_len = len(parameter_hash)
        if hash_len != self.__OWEN_PARAM_HASH_LEN:
            raise ValueError(
                self.__HASH_LEN_ERR_MSG.format(
                    actual=hash_len, expected=self.__OWEN_PARAM_HASH_LEN
                )
            )
        # адрес + hash параметра счетчика
        data: bytearray = bytearray(self.addr) + parameter_hash
        # устанавливаем бит запроса, размер блока данных = 0
        data[1] |= 0x10
        # добавляем CRC
        data += self.calc_owen_crc(data)
        return data

    def bin_to_ascii(self, data: bytearray) -> bytearray:
        """
        Преобразует двоичный пакет в ASCII.
        Каждая тетрада пакета заменяется на ASCII символ с кодом 0x47 - 0x56.
        Добавляет символы начала и окончания пакета.
        """
        ascii_packet = bytearray(self.__OWEN_PACKET_HEADER)
        for byte in data:
            byte = int(byte)
            h_nibble = ((byte & 0xF0) >> 4) + self.__OWEN_ASCII_LOWEST_CODE
            l_nibble = (byte & 0x0F) + self.__OWEN_ASCII_LOWEST_CODE
            ascii_packet.append(h_nibble)
            ascii_packet.append(l_nibble)
        ascii_packet.append(self.__OWEN_PACKET_FOOTER[0])
        return ascii_packet

    def ascii_to_bin(self, data: bytes) -> bytearray:
        """
        Преобразует ASCII пакет в двоичный.
        Вызывает исключения при ошибках.
        """

        try:
            if data[0] != ord(self.__OWEN_PACKET_HEADER):
                raise PacketHeaderError(packet=data)
            if data[-1] != ord(self.__OWEN_PACKET_FOOTER):
                raise PacketFooterError(packet=data)
            bin_packet = bytearray()
            for i in range(1, len(data) - 1, 2):
                l_nibble = data[i + 1]
                h_nibble = data[i]
                if not (
                    self.__OWEN_ASCII_LOWEST_CODE
                    <= l_nibble
                    <= self.__OWEN_ASCII_HIGHEST_CODE
                ) or not (
                    self.__OWEN_ASCII_LOWEST_CODE
                    <= h_nibble
                    <= self.__OWEN_ASCII_HIGHEST_CODE
                ):
                    raise PacketDecodeError(
                        packet=data, msg='Пакет содержит недопустимый символ'
                    )
                l_nibble -= self.__OWEN_ASCII_LOWEST_CODE
                h_nibble -= self.__OWEN_ASCII_LOWEST_CODE
                bin_packet.append((h_nibble << 4) | l_nibble)
            return bin_packet
        except IndexError:
            raise PacketDecodeError(
                packet=data, msg='Недопустимая длина полученного пакета'
            ) from None

    def check_bin_packet(self, data: bytearray, parameter_hash: bytes) -> bytearray:
        """
        Проверяет валидность пакета и возвращает извлеченный блок данных.
        Поднимает исключение если пакет не валиден.
        """
        try:
            # проверяем CRC
            actual_crc = data[self.__OWEN_CRC_BYTES]
            calculated_crc = self.calc_owen_crc(data[self.__OWEN_CRC_DATA_BYTES])
            if actual_crc != calculated_crc:
                raise PacketDecodeError(
                    packet=bytes(data),
                    msg=self.__RESPONSE_CRC_ERR_MSG.format(
                        actual=bytes(actual_crc), expected=calculated_crc
                    ),
                )
            # проверяем адрес устройства
            packet_addr = data[self.__OWEN_ADDR_BYTES]
            packet_addr[1] &= 0xE0
            if packet_addr != self.addr:
                raise PacketDecodeError(
                    packet=bytes(data),
                    msg=self.__RESPONSE_ADDR_ERR_MSG.format(
                        actual=bytes(packet_addr), expected=self.addr
                    ),
                )
            # проверяем hash параметра
            actual_hash = data[self.__OWEN_HASH_BYTES]
            if parameter_hash != actual_hash:
                raise PacketDecodeError(
                    packet=bytes(data),
                    msg=self.__RESPONSE_HASH_ERR_MSG.format(
                        actual=bytes(actual_hash), expected=parameter_hash
                    ),
                )
            return data[self.__OWEN_DATA_BYTES]
        except IndexError:
            raise PacketLenError(packet=data) from None

    def read_parameter(self, serial_if: Serial, parameter_hash: bytes):
        """
        Считывает параметр счетчика импульсов.
        :param serial_if: Порт.
        :param parameter_hash: Hash параметра счетчика.
        :return: Значение параметра.
        """
        if parameter_hash not in (self.DCNT, self.DSPD, self.DTMR):
            raise ValueError(self.__HASH_ERR_MSG.format(actual=parameter_hash))
        serial_if.reset_input_buffer()
        serial_if.write(self.bin_to_ascii(self.get_command_packet(parameter_hash)))
        serial_if.flush()
        response_expected_len = self.PARAMS[parameter_hash]['response_len']
        ascii_response = serial_if.read(response_expected_len)
        if not ascii_response:
            raise TimeoutError

        data = self.check_bin_packet(self.ascii_to_bin(ascii_response), parameter_hash)
        if len(data) == 0:
            raise PacketLenError(packet=ascii_response)

        return self.PARAMS[parameter_hash]['converter'](data=data)
