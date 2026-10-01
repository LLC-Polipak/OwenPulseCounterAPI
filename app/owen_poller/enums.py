from enum import Enum


class SensorStatus(str, Enum):
    """
    Перечисление всех возможных состояний логического датчика.
    Наследование от str позволяет FastAPI/Pydantic/json автоматически
    сериализовать их в обычные строки при отправке ответа.
    """

    OK = 'OK'
    STOP = 'STOP'
    UNKNOWN = 'UNKNOWN'
    OFFLINE = 'OFFLINE'
    NOT_FOUND = 'NOT_FOUND'
