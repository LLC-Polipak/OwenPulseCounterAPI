"""Пользовательские исключения модуля опроса устройств."""


class DeviceNotFound(Exception):
    """Исключение при запросе устройства, отсутствующего в конфигурации settings.py."""

    def __init__(self, device_name):
        super().__init__(f'Устройство "{device_name}" не найдено')
