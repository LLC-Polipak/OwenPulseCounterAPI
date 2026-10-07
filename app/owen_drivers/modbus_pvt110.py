import logging
import struct
import time
from typing import Any

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
    poll_interval = 10.0

    min_success_rate: float = 0.25

    __FAILED_ATTEMPTS: int = 3

    # Адреса регистров (согласно конфигуратору)
    __REG_TEMPERATURE: int = 2250  # 0x08CA
    __REG_HUMIDITY: int = 2200  # 0x0898

    __REG_STATUS: int = 1300
    __REG_REBOOT: int = 1400

    __REBOOT_CMD_VALUE: int = 1
    __REGS_INT16_COUNT: int = 1

    # Настройки протокола Modbus
    __FUNC_READ_HOLDING_REGISTERS: int = 3
    __FUNC_WRITE_SINGLE_REGISTER: int = 6
    __REGS_FLOAT32_COUNT: int = 2

    __FLOAT32_RESPONSE_EXPECTED_LEN: int = 9
    __INT32_RESPONSE_EXPECTED_LEN: int = 7

    # Ответ с ошибкой содержит код функции
    __MODBUS_ERROR_OFFSET: int = 0x80

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
    __FORMAT_INT: str = '>H'

    # Срезы для парсинга байтовых ответов
    __PAYLOAD_FLOAT32_SLICE: slice = slice(3, 7)
    __PAYLOAD_INT16_SLICE: slice = slice(3, 5)
    __CRC_RECEIVED_SLICE: slice = slice(-2, None)
    __CRC_CALC_DATA_SLICE: slice = slice(0, -2)
    __WORD1_SLICE: slice = slice(0, 2)
    __WORD2_SLICE: slice = slice(2, 4)

    # Задержка
    __READ_DELAY: float = 0

    # Ключи для результирующего словаря
    __KEY_TEMPERATURE: str = 'temperature'
    __KEY_HUMIDITY: str = 'humidity'
    __KEY_HW_CODE: str = 'hardware_code'
    __KEY_HW_IS_OK: str = 'is_ok'
    __KEY_HW_DESC: str = 'description'

    def __init__(self, addr: int, **kwargs):
        """
        Инициализация драйвера.

        :param addr: Сетевой адрес устройства Modbus.
        :param kwargs: Дополнительные параметры не используются в этом драйвере.
        """
        super().__init__(addr, **kwargs)

    def _execute_modbus_command(
        self,
        provider: BaseDataProvider,
        func_code: int,
        reg_addr: int,
        payload: int,
        expected_len: int,
    ) -> bytes:
        """
        Формирует пакет, отправляет его, читает ответ, проверяя все ошибки протокола.

        :param provider: Провайдер связи (COM-порт или Mock).
        :param func_code: Код функции Modbus (0x03, 0x06 и т.д.).
        :param reg_addr: Адрес регистра.
        :param payload: Для функции 0x03 — количество регистров, для 0x06 — значение.
        :param expected_len: Ожидаемая длина ответа в байтах (0 = не ждать ответа).
        :return: Валидный массив байт ответа (без ошибок) или пустые байты.
        """
        request = struct.pack(
            self.__FORMAT_REQUEST, self.addr, func_code, reg_addr, payload
        )
        crc = self._calculate_crc(request)
        request += struct.pack(self.__FORMAT_CRC, crc)

        provider.clear_buffers()
        provider.write(request)
        time.sleep(self.__READ_DELAY)

        response = provider.read(expected_len)

        if expected_len == 0:
            return b''

        if len(response) == 0:
            raise TimeoutError(f'ПВТ-110 (адрес {self.addr}) не ответил.')

        if response[1] == (func_code + self.__MODBUS_ERROR_OFFSET):
            error_code = response[2] if len(response) > 2 else -1
            error_msg = self.MODBUS_ERRORS.get(error_code, 'Неизвестная ошибка')
            raise ModbusProtocolError(f'Код {error_code} - {error_msg}')

        if len(response) < expected_len:
            raise PacketLenError(response)

        received_crc = struct.unpack(
            self.__FORMAT_CRC, response[self.__CRC_RECEIVED_SLICE]
        )[0]
        if received_crc != self._calculate_crc(response[self.__CRC_CALC_DATA_SLICE]):
            raise CRCCheckError(response)

        return response

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
        response = self._execute_modbus_command(
            provider=provider,
            func_code=self.__FUNC_READ_HOLDING_REGISTERS,
            reg_addr=register_addr,
            payload=self.__REGS_FLOAT32_COUNT,
            expected_len=self.__FLOAT32_RESPONSE_EXPECTED_LEN,
        )

        payload_bytes = response[self.__PAYLOAD_FLOAT32_SLICE]
        cdab_payload = (
            payload_bytes[self.__WORD2_SLICE] + payload_bytes[self.__WORD1_SLICE]
        )
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

    def reboot(self, provider: 'BaseDataProvider') -> bool:
        """Отправляет команду программной перезагрузки ПВТ-110 (функция 0x06)."""
        try:
            self._execute_modbus_command(
                provider=provider,
                func_code=self.__FUNC_WRITE_SINGLE_REGISTER,
                reg_addr=self.__REG_REBOOT,
                payload=self.__REBOOT_CMD_VALUE,
                expected_len=0,
            )
            return True
        except Exception as e:
            logger.warning(f'Ошибка отправки команды перезагрузки ПВТ-110: {e}')
            return False

    def read_device_status(self, provider: 'BaseDataProvider') -> dict[str, Any] | None:
        """Чтение аппаратного кода ошибки (например, обрыв сенсора внутри ПВТ)."""
        try:
            response = self._execute_modbus_command(
                provider=provider,
                func_code=self.__FUNC_READ_HOLDING_REGISTERS,
                reg_addr=self.__REG_STATUS,
                payload=self.__REGS_INT16_COUNT,
                expected_len=self.__INT32_RESPONSE_EXPECTED_LEN,
            )

            status_code = struct.unpack(
                self.__FORMAT_INT, response[self.__PAYLOAD_INT16_SLICE]
            )[0]
            is_ok = status_code == 0

            return {
                self.__KEY_HW_CODE: status_code,
                self.__KEY_HW_IS_OK: is_ok,
                self.__KEY_HW_DESC: 'Норма'
                if is_ok
                else f'Ошибка ПВТ код {status_code}',
            }
        except Exception as e:
            logger.warning(f'Ошибка чтения аппаратного статуса ПВТ-110: {e}')
            return None
