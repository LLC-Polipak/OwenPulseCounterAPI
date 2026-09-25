class DeviceNotFound(Exception):
    """
    Исключение, возникающее при попытке запросить данные
    устройства, которого нет в конфигурации settings.py.
    """

    def __init__(self, device_name):
        super().__init__(f'Устройство "{device_name}" не найдено')
