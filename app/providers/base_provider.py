from abc import ABC, abstractmethod


class BaseDataProvider(ABC):
    """Абстрактный интерфейс для любого поставщика данных (COM-порт, TCP/IP, Mock)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Возвращает имя подключения (например, 'COM1' или 'Mock-1')."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Открывает соединение."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Закрывает соединение."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверяет, активно ли соединение."""
        pass

    @abstractmethod
    def clear_buffers(self) -> None:
        """Очищает входные и выходные буферы."""
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Отправляет данные в канал."""
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        """Читает заданное количество байт из канала."""
        pass
