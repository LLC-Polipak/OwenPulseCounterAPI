import logging
from datetime import datetime

from serial import Serial, SerialException

from app.providers.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class SerialDataProvider(BaseDataProvider):
    """Реализация поставщика данных для физического RS-485 через COM-порт."""

    def __init__(self, settings: dict, reconnect_interval: float = 10.0):
        self.settings: dict = settings
        self._serial: Serial | None = None

        self.reconnect_interval: float = reconnect_interval
        self._last_attempt_ts: datetime | None = None

    @property
    def name(self) -> str:
        return self._serial.port or 'Unknown_COM'

    def connect(self) -> bool:
        if self._serial and self._serial.is_open:
            return True

        if not self.settings:
            return False

        now = datetime.now()

        if self._last_attempt_ts is not None:
            seconds_passed = (now - self._last_attempt_ts).total_seconds()
            if seconds_passed < self.reconnect_interval:
                return False

        self._last_attempt_ts = now

        try:
            if self._serial is None:
                kwargs = self.settings.copy()
                self._serial = Serial(**kwargs)

            logger.info(f'Попытка подключения к порту {self._serial.port}...')
            self._serial.open()
            logger.info('Соединение с портом успешно установлено!')
            return True
        except SerialException as e:
            logger.error(
                f'COM-порт недоступен (повтор через {self.reconnect_interval}с): {e}'
            )
            return False

    def disconnect(self) -> None:
        if self._serial.is_open:
            self._serial.close()
            self._last_attempt_ts = datetime.now()

    @property
    def is_connected(self) -> bool:
        return self._serial.is_open

    def clear_buffers(self) -> None:
        if self.is_connected:
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

    def write(self, data: bytes) -> None:
        self._serial.write(data)

    def read(self, size: int) -> bytes:
        return self._serial.read(size)
