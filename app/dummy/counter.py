import random

from serial import Serial


class DummyCounter:
    """
    Фейковый счетчик для отладки.
    """

    def __init__(self, addr: int, addr_len: int = 8):
        """
        :param addr: адрес счетчика СИ8,
        :param addr_len: длина адреса.
        """
        self.__total_reading = 0
        work = [random.randint(150, 200) for _ in range(2 * random.randint(9, 10))]
        part_work = [random.randint(10, 100) for _ in range(2 * random.randint(5, 7))]
        pause = [random.randint(0, 9) for _ in range(2 * random.randint(2, 9))]
        stop = [random.randint(0, 9) for _ in range(2 * random.randint(11, 20))]
        offline = [None for _ in range(2 * random.randint(9, 12))]
        self.__values = (
            offline
            + stop
            + part_work
            + pause
            + stop
            + work
            + pause
            + part_work
            + work
            + stop
            + work
            + stop
            + offline
        )
        self.__index = 0

    def read_parameter(self, serial_if: Serial, parameter_hash: bytes):
        """
        Считывает параметр счетчика импульсов.
        :param serial_if: Порт.
        :param parameter_hash: Hash параметра счетчика.
        :return: Значение параметра.
        """

        value = self.__values[self.__index]

        self.__index += 1
        if self.__index >= len(self.__values):
            self.__index = 0

        if value is None:
            return value
        self.__total_reading += value
        return self.__total_reading
