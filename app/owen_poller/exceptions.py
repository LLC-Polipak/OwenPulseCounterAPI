"""Пользовательские исключения модуля опроса устройств."""


class DeviceNotFound(Exception):
    """Исключение при запросе устройства, отсутствующего в конфигурации."""

    def __init__(self, device_name: str):
        super().__init__(f'Устройство "{device_name}" не найдено')


class DeviceAddressAlreadyExists(Exception):
    """Исключение при попытке добавить устройство с уже занятым сетевым адресом."""

    def __init__(self, addr: int):
        super().__init__(f'Устройство с адресом {addr} уже существует в списке опроса.')


class DeviceNameAlreadyExists(Exception):
    """Исключение при попытке добавить устройство с уже существующим именем."""

    def __init__(self, name: str):
        super().__init__(f'Устройство с именем "{name}" уже существует.')
