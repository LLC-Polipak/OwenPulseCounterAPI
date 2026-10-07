from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.owen_poller.enums import SensorStatus
from app.owen_poller.state import SensorMinuteSnapshot, SensorRuntimeState


class BaseFormatter(ABC):
    """
    Абстрактный интерфейс для форматирования данных сенсора.
    Обеспечивает разделение логики работы с оборудованием (Драйвер)
    и логики представления данных для внешних API (Форматтер).
    """

    @abstractmethod
    def format_instant(
        self, name: str, metric: Any, status: SensorStatus, measured_at: datetime
    ) -> dict:
        """
        Форматирует мгновенный ответ для обработки запросов к API в реальном времени.

        :param name: Имя сенсора.
        :param metric: Вычисленная метрика (скорость, абсолютное значение или словарь).
        :param status: Логический статус сенсора.
        :param measured_at: Временная метка вычисления.
        :return: Словарь, готовый к JSON-сериализации.
        """
        pass

    @abstractmethod
    def format_snapshot(
        self, name: str, snapshot: SensorMinuteSnapshot, state: SensorRuntimeState
    ) -> dict:
        """
        Форматирует минутный снимок (Snapshot) состояния сенсора.

        :param name: Имя сенсора.
        :param snapshot: Зафиксированный минутный снимок.
        :param state: Текущее runtime-состояние (используется для извлечения абсолютных значений).
        :return: Словарь с минутным отчетом.
        """
        pass

    @abstractmethod
    def format_telemetry(self, name: str, metric: Any) -> dict:
        """
        Форматирует компактную полезную нагрузку (payload) для отправки в фоновом режиме.

        :param name: Имя сенсора.
        :param metric: Вычисленная метрика (скорость, абсолютное значение или словарь).
        :return: Компактный словарь только с необходимыми метриками.
        """
        pass


class CounterFormatter(BaseFormatter):
    """
    Форматтер для накопительных счетчиков (например, ОВЕН СИ8).
    Возвращает данные в виде одного ключа 'value' и передает
    абсолютные значения счетчика (true_value) в минутных отчетах.
    """

    def format_instant(
        self, name: str, metric: float, status: SensorStatus, measured_at: datetime
    ) -> dict:
        return {
            'sensor': name,
            'value': metric,
            'measured_at': measured_at,
            'status': status,
        }

    def format_snapshot(
        self, name: str, snapshot: SensorMinuteSnapshot, state: SensorRuntimeState
    ) -> dict:
        return {
            'sensor': name,
            'status': snapshot.status,
            'value': snapshot.value,
            'true_value': state.last_value,
            'measured_at': snapshot.minute,
            'changed_at': snapshot.last_seen_at,
            'success_rate': snapshot.success_rate,
        }

    def format_telemetry(self, name: str, metric: float) -> dict:
        return {'sensor': name, 'value': metric}


class EnvironmentFormatter(BaseFormatter):
    """
    Форматтер для датчиков микроклимата и среды (например, ПВТ-110).
    Распаковывает словари метрик (temperature, humidity) на верхний уровень ответа.
    Не передает дублирующий true_value в минутных отчетах.
    """

    def format_instant(
        self,
        name: str,
        metric: dict | None,
        status: SensorStatus,
        measured_at: datetime,
    ) -> dict:
        response = {'sensor': name, 'measured_at': measured_at, 'status': status}
        if isinstance(metric, dict):
            response.update(metric)
        return response

    def format_snapshot(
        self, name: str, snapshot: SensorMinuteSnapshot, state: SensorRuntimeState
    ) -> dict:
        response = {
            'sensor': name,
            'status': snapshot.status,
            'measured_at': snapshot.minute,
            'changed_at': snapshot.last_seen_at,
            'success_rate': snapshot.success_rate,
        }
        if isinstance(snapshot.value, dict):
            response.update(snapshot.value)

        return response

    def format_telemetry(self, name: str, metric: dict | None) -> dict:
        payload = {'sensor': name}
        if isinstance(metric, dict):
            payload.update(metric)
        return payload
