class ImproperlyConfiguredError(Exception):
    """Исключение при неверной конфигурации параметров устройства."""

    def __init__(self, message):
        super().__init__(self, f'Неверная конфигурация устройства. {message}')


class PacketHeaderError(Exception):
    """Исключение, возникающее при получении пакета с неверным символом начала."""

    def __init__(self, packet):
        super().__init__(self, f'Получен пакет с неверным заголовком - {packet}.')


class PacketFooterError(Exception):
    """Исключение, возникающее при получении пакета с неверным символом окончания."""

    def __init__(self, packet):
        super().__init__(self, f'Получен пакет с неверным окончанием - {packet}.')


class PacketDecodeError(Exception):
    """Исключение при невозможности раскодировать тело пакета."""

    def __init__(self, packet, msg):
        super().__init__(
            self,
            (
                f'Ошибка декодирования пакета полученного от '
                f'устройства: {packet} {packet}. {msg}'
            ),
        )


class PacketLenError(Exception):
    """Исключение при получении пакета недостаточной или избыточной длины."""

    def __init__(self, packet):
        super().__init__(self, f'Недопустимая длина пакета {packet} :({len(packet)})')


class BCDValueError(Exception):
    """Исключение при неудачной попытке преобразования BCD-данных в целое число."""

    def __init__(self, data):
        super().__init__(
            self, f'Не удалось преобразовать значение {data} в целое число.'
        )


class TimeValueError(Exception):
    """Исключение при неудачной попытке преобразования данных во временной интервал."""

    def __init__(self, data):
        super().__init__(
            self, f'Не удалось преобразовать значение {data} во временной интервал.'
        )


class CRCCheckError(Exception):
    """Исключение при несовпадении вычисленной и полученной контрольной суммы."""

    def __init__(self, packet):
        super().__init__(
            self, f'Ошибка контрольной суммы (CRC) в пакете: {packet.hex(" ")}'
        )


class ModbusProtocolError(Exception):
    """Исключение, возникающее, если устройство Modbus возвращает код ошибки."""

    def __init__(self, msg):
        super().__init__(self, f'Ошибка протокола Modbus: {msg}')
