"""Абстрактный базовый класс для поставщиков данных (провайдеров связи)."""

from abc import ABC, abstractmethod


class BaseDataProvider(ABC):
    """Абстрактный интерфейс для любого поставщика данных (COM-порт, TCP/IP, Mock)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Вернуть имя подключения (например, 'COM1' или 'Mock-1')."""

    @abstractmethod
    def connect(self) -> bool:
        """Открыть соединение."""

    @abstractmethod
    def disconnect(self) -> None:
        """Закрыть соединение."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверить, активно ли соединение."""

    @abstractmethod
    def clear_buffers(self) -> None:
        """Очистить входные и выходные буферы."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Отправить данные в канал."""

    @abstractmethod
    def read(self, size: int) -> bytes:
        """Прочитать заданное количество байт из канала."""
