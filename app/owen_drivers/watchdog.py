"""Программный сторожевой таймер для контроля зависания показаний датчиков."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FrozenValueWatchdog:
    """Программный сторожевой таймер для отслеживания «заморозки» данных.

    Анализирует поток данных (I2C Bus Lockup): если значения не меняются
    заданное количество раз подряд, сигнализирует о зависании оборудования.
    """

    def __init__(self, threshold: int = 20):
        self.threshold = threshold
        self._frozen_count = 0
        self._last_value: Any = None

    def feed(self, current_value: Any) -> bool:
        """Передать сторожевому таймеру новое считанное значение.

        Args:
            current_value: Текущее считанное значение (Float, Dict и т.д.).

        Returns:
            True, если обнаружено зависание. Иначе False.
        """
        if current_value is None:
            return False

        if self._last_value == current_value:
            self._frozen_count += 1
        else:
            self._frozen_count = 0
            self._last_value = current_value

        if self._frozen_count >= self.threshold:
            logger.error(
                'Watchdog: Обнаружено зависание данных (значение не меняется).'
            )
            self._frozen_count = 0
            return True

        return False
