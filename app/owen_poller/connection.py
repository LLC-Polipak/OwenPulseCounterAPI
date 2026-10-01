from app.providers.base_provider import BaseDataProvider
from app.providers.mock_provider import MockDataProvider
from app.providers.serial_provider import SerialDataProvider


class ConnectionManager:
    """Управляет физическим соединением (COM-портом)."""

    def __init__(self, settings: dict | None, use_mock: bool = False):
        self.provider: BaseDataProvider

        if use_mock:
            self.provider = MockDataProvider()
        else:
            self.provider = SerialDataProvider(settings or {})

    def connect(self) -> bool:
        """Обеспечивает подключение. Возвращает True, если порт готов к обмену."""
        return self.provider.connect()

    def disconnect(self) -> None:
        """Принудительно закрывает порт."""
        self.provider.disconnect()
