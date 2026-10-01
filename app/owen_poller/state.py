from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from app.owen_poller.enums import SensorStatus

if TYPE_CHECKING:
    from app.owen_drivers.base_driver import BaseDriver

OFFLINE_THRESHOLD = 60


@dataclass
class SensorRuntimeState:
    """
    Богатая модель (Rich Domain Model) состояния сенсора.
    Инкапсулирует данные о попытках чтения и логику вычисления собственных статусов.
    """

    last_value: float | int | None = None
    last_ts: datetime | None = None

    last_poll_attempt_ts: datetime | None = None

    current_minute: datetime | None = None
    minute_start_value: float | int | None = None
    minute_end_value: float | int | None = None

    attempt_count: int = 0
    success_count: int = 0
    consecutive_fails: int = 0

    last_success_ts: datetime | None = None

    last_minute_snapshot: Optional['SensorMinuteSnapshot'] = None

    def add_success(self, value: Any, timestamp: datetime) -> None:
        """
        Регистрирует успешное получение данных от прибора.
        Сбрасывает счетчик ошибок подряд и обновляет минутные рамки (start/end_value).

        :param value: Полученное значение (число, словарь и т.д.).
        :param timestamp: Время получения значения.
        """
        self.attempt_count += 1
        self.success_count += 1
        self.consecutive_fails = 0

        self.last_value = value
        self.last_success_ts = timestamp
        self.last_ts = timestamp

        if self.minute_start_value is None:
            self.minute_start_value = value
        self.minute_end_value = value

    def add_fail(self) -> None:
        """
        Регистрирует неудачную попытку опроса (ошибка CRC, таймаут, пустой ответ).

        Увеличивает счетчик общего количества попыток и количество ошибок подряд.
        """
        self.attempt_count += 1
        self.consecutive_fails += 1

    def check_minute_boundary(
        self, current_time: datetime, device: 'BaseDriver'
    ) -> None:
        """
        Проверяет, не наступила ли новая минута.

        Если минута сменилась, вызывает метод финализации прошлой минуты
        и сбрасывает все счетчики попыток.

        :param current_time: Текущее время (обычно datetime.now()).
        :param device: Ссылка на драйвер прибора для делегирования расчетов.
        """
        minute = current_time.replace(second=0, microsecond=0)
        if self.current_minute != minute:
            if self.current_minute is not None:
                self._finalize_minute(device)

            self.current_minute = minute
            self.minute_start_value = None
            self.minute_end_value = None
            self.success_count = 0
            self.attempt_count = 0

    def _finalize_minute(self, device: 'BaseDriver') -> None:
        """
        Закрывает прошедшую минуту.

        Запрашивает у драйвера расчет разницы показаний и статуса,
        а затем сохраняет результат в last_minute_snapshot.

        :param device: Ссылка на драйвер прибора.
        """
        diff = device.calculate_minute_metric(
            self.minute_start_value, self.minute_end_value
        )
        status = device.get_status(diff, self)

        success_rate = device.calculate_success_rate(
            self.attempt_count, self.success_count
        )

        self.last_minute_snapshot = SensorMinuteSnapshot(
            minute=self.current_minute,
            value=diff,
            status=status,
            success_rate=success_rate,
            last_seen_at=self.last_success_ts,
        )


@dataclass
class SensorMinuteSnapshot:
    """
    Фиксированный "снимок" состояния сенсора по окончании минуты.
    Используется для отправки исторической отчетности.
    """

    minute: datetime

    value: float | int | None
    status: SensorStatus

    success_rate: float
    last_seen_at: datetime | None
