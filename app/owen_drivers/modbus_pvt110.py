import logging
import struct
import time

from app.owen_drivers.base_driver import BaseDriver
from app.owen_drivers.exceptions import (
    CRCCheckError,
    ModbusProtocolError,
    PacketLenError,
)
from app.owen_poller.enums import SensorStatus
from app.owen_poller.state import SensorRuntimeState
from app.providers.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class ModbusPVT110(BaseDriver):
    """
    Драйвер для работы с термогигрометром ОВЕН ПВТ-110 по протоколу Modbus RTU.
    Осуществляет последовательное чтение регистров температуры и влажности.
    """

    poll_priority = 1
    poll_interval = 5.0

    min_success_rate: float = 0.25

    __FAILED_ATTEMPTS: int = 3

    # Адреса регистров (согласно конфигуратору)
    __REG_TEMPERATURE: int = 2250  # 0x08CA
    __REG_HUMIDITY: int = 2200  # 0x0898

    # Настройки протокола Modbus
    __FUNC_READ_HOLDING_REGISTERS: int = 3
    __REGS_TO_READ: int = 2
    __RESPONSE_EXPECTED_LEN: int = 9

    # Ответ с ошибкой содержит код функции
    __MODBUS_ERROR_FUNC_CODE: int = 0x83

    # Стандартные коды ошибок Modbus
    MODBUS_ERRORS: dict[int, str] = {
        1: 'Illegal Function',
        2: 'Illegal Data Address',
        3: 'Illegal Data Value',
        4: 'Slave Device Failure',
    }

    # Константы для расчета CRC
    __CRC_INIT: int = 0xFFFF
    __CRC_POLYNOMIAL: int = 0xA001

    # Форматы упаковки/распаковки
    __FORMAT_REQUEST: str = '>BBHH'
    __FORMAT_CRC: str = '<H'
    __FORMAT_FLOAT: str = '>f'

    # Срезы для парсинга байтовых ответов
    __PAYLOAD_SLICE: slice = slice(3, 7)
    __CRC_RECEIVED_SLICE: slice = slice(-2, None)
    __CRC_CALC_DATA_SLICE: slice = slice(0, -2)
    __WORD1_SLICE: slice = slice(0, 2)
    __WORD2_SLICE: slice = slice(2, 4)

    # Задержка
    __READ_DELAY: float = 0

    # Ключи для результирующего словаря
    __KEY_TEMPERATURE: str = 'temperature'
    __KEY_HUMIDITY: str = 'humidity'

    def __init__(self, addr: int, **kwargs):
        """
        Инициализация драйвера.

        :param addr: Сетевой адрес устройства Modbus.
        :param kwargs: Дополнительные параметры не используются в этом драйвере.
        """
        super().__init__(addr, **kwargs)

    def _calculate_crc(self, data: bytes) -> int:
        """
        Рассчитывает контрольную сумму CRC16 для протокола Modbus RTU.

        :param data: Пакет байтов для расчета.
        :return: Вычисленное значение CRC.
        """
        crc = self.__CRC_INIT
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= self.__CRC_POLYNOMIAL
                else:
                    crc >>= 1
        return crc

    def _read_register(
        self, provider: BaseDataProvider, register_addr: int
    ) -> float | None:
        """
        Выполняет низкоуровневый запрос по Modbus RTU для чтения Float 32 (2 регистра).

        :param provider: Поставщик данных.
        :param register_addr: Начальный адрес регистра для чтения.
        :return: Распакованное значение с плавающей точкой или None при ошибке связи.
        """
        request = struct.pack(
            self.__FORMAT_REQUEST,
            self.addr,
            self.__FUNC_READ_HOLDING_REGISTERS,
            register_addr,
            self.__REGS_TO_READ,
        )
        crc = self._calculate_crc(request)
        request += struct.pack(self.__FORMAT_CRC, crc)

        provider.clear_buffers()
        provider.write(request)
        time.sleep(self.__READ_DELAY)

        response = provider.read(self.__RESPONSE_EXPECTED_LEN)

        if len(response) == 0:
            raise TimeoutError(f'ПВТ-110 (адрес {self.addr}) не ответил.')

        if response[1] == self.__MODBUS_ERROR_FUNC_CODE:
            error_code = response[2] if len(response) > 2 else -1
            error_msg = self.MODBUS_ERRORS.get(error_code, 'Неизвестная ошибка')
            raise ModbusProtocolError(f'Код {error_code} - {error_msg}')

        if len(response) < self.__RESPONSE_EXPECTED_LEN:
            raise PacketLenError(response)

        received_crc = struct.unpack(
            self.__FORMAT_CRC, response[self.__CRC_RECEIVED_SLICE]
        )[0]
        if received_crc != self._calculate_crc(response[self.__CRC_CALC_DATA_SLICE]):
            raise CRCCheckError(response)

        payload = response[self.__PAYLOAD_SLICE]
        cdab_payload = payload[self.__WORD2_SLICE] + payload[self.__WORD1_SLICE]
        value = struct.unpack(self.__FORMAT_FLOAT, cdab_payload)[0]

        return round(value, 2)

    def read_parameter(
        self, provider: BaseDataProvider, **kwargs
    ) -> dict[str, float] | None:
        """
        Считывает оба параметра с прибора: температуру и влажность.

        :param provider: Поставщик данных.
        :param kwargs: Не используется в данном драйвере.
        :return: Словарь со значениями температуры и влажности, либо None в случае сбоя.
        """
        try:
            temperature = self._read_register(provider, self.__REG_TEMPERATURE)
            if temperature is None:
                return None

            time.sleep(self.__READ_DELAY)

            humidity = self._read_register(provider, self.__REG_HUMIDITY)
            if humidity is None:
                return None

            return {self.__KEY_TEMPERATURE: temperature, self.__KEY_HUMIDITY: humidity}

        except Exception as e:
            logger.error(f'Modbus PVT110 Error: {e}')
            return None

    def calculate_minute_metric(
        self, start_val: dict | None, end_val: dict | None
    ) -> dict | None:
        """
        Возвращает последние показания.

        Для термогигрометра минутным итогом является просто последнее
        зафиксированное значение температуры и влажности.
        """
        return end_val

    def calculate_instant_metric(
        self, curr_val: dict, prev_val: dict, duration_sec: float
    ) -> dict:
        """
        Возвращает текущие значения.

        Для термогигрометра понятие скорости не применимо, поэтому
        внешним системам всегда отдаются текущие абсолютные показания.
        """
        return curr_val

    def get_status(
        self, metric: dict | None, state: SensorRuntimeState
    ) -> SensorStatus:
        """
        Анализирует работоспособность термогигрометра.

        Переводит в OFFLINE только при достижении кол-ва ошибок, заданных в FAILED_ATTEMPTS.
        Термогигрометр не имеет состояния STOP.
        """
        if state.consecutive_fails >= self.__FAILED_ATTEMPTS:
            return SensorStatus.OFFLINE

        rate = self.calculate_success_rate(state.attempt_count, state.success_count)
        if state.attempt_count > 0 and rate < self.min_success_rate:
            return SensorStatus.UNKNOWN

        if metric is None:
            return SensorStatus.UNKNOWN
        return SensorStatus.OK
