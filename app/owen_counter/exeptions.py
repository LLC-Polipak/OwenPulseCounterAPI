class ImproperlyConfiguredError(Exception):
    def __init__(self, message):
        super().__init__(self, f'Неверная конфигурация устройства. {message}')


class PacketHeaderError(Exception):
    def __init__(self, packet):
        super().__init__(self, f'Получен пакет с неверным заголовком - {packet}.')


class PacketFooterError(Exception):
    def __init__(self, packet):
        super().__init__(self, f'Получен пакет с неверным окончанием - {packet}.')


class PacketDecodeError(Exception):
    def __init__(self, packet, msg):
        super().__init__(
            self,
            (
                f'Ошибка декодирования пакета полученного от '
                f'устройства: {packet} {packet}. {msg}'
            ),
        )


class PacketLenError(Exception):
    def __init__(self, packet):
        super().__init__(self, f'Недопустимая длина пакета {packet} :({len(packet)})')


class BCDValueError(Exception):
    def __init__(self, data):
        super().__init__(
            self, f'Не удалось преобразовать значение {data} в целое число.'
        )


class TimeValueError(Exception):
    def __init__(self, data):
        super().__init__(
            self, f'Не удалось преобразовать значение {data} во временной интервал.'
        )
