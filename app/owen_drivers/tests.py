import unittest
from collections import namedtuple
from datetime import timedelta

from .exeptions import (
    BCDValueError,
    ImproperlyConfiguredError,
    PacketDecodeError,
    PacketHeaderError,
)
from .owen_ci8 import DataConverters, OwenCI8


class TestOwenCounter(unittest.TestCase):
    def test_init_with_invalid_addr_len(self):
        """Тестируем конструктор с невалидными значениями addr_len."""
        valid_values = (8, 11)
        for no_valid_value in range(-1, 33):
            if no_valid_value in valid_values:
                continue
            with (
                self.subTest(addr_len=no_valid_value),
                self.assertRaises(
                    ImproperlyConfiguredError,
                    msg='Конструктор не поднимает исключение!',
                ),
            ):
                OwenCI8(addr=0, addr_len=no_valid_value)

    def test_init_with_invalid_addr(self):
        """Тестируем конструктор с невалидными значениями addr."""
        Fixture = namedtuple('Fixture', ['addr', 'addr_len'])
        fixtures = [
            Fixture(addr=-1, addr_len=8),
            Fixture(addr=256, addr_len=8),
            Fixture(addr=-1, addr_len=11),
            Fixture(addr=2048, addr_len=11),
        ]
        for fixture in fixtures:
            with (
                self.subTest(
                    addr=fixture.addr,
                    addr_len=fixture.addr_len,
                ),
                self.assertRaises(
                    ImproperlyConfiguredError,
                    msg='Конструктор не поднимает исключение!',
                ),
            ):
                OwenCI8(addr=fixture.addr, addr_len=fixture.addr_len)

    def test_init_addr_translation(self):
        """Тестируем трансляцию addr конструктором."""
        Fixture = namedtuple('Fixture', ['addr', 'addr_len', 'addr_translated'])
        fixtures = [
            Fixture(addr=0x00, addr_len=8, addr_translated=b'\x00\x00'),
            Fixture(addr=0xFF, addr_len=8, addr_translated=b'\xff\x00'),
            Fixture(addr=0xA3, addr_len=8, addr_translated=b'\xa3\x00'),
            Fixture(addr=0x00, addr_len=11, addr_translated=b'\x00\x00'),
            Fixture(addr=0x7FF, addr_len=11, addr_translated=b'\xff\xe0'),
            Fixture(addr=0x555, addr_len=11, addr_translated=b'\xaa\xa0'),
        ]
        for fixture in fixtures:
            instance = OwenCI8(addr=fixture.addr, addr_len=fixture.addr_len)
            with self.subTest(
                addr=fixture.addr,
                addr_len=fixture.addr_len,
                addr_translated=fixture.addr_translated,
            ):
                self.assertEqual(
                    fixture.addr_translated,
                    instance.addr,
                    'Неверное значение self.addr.',
                )

    def test_calc_owen_crc(self):
        """Тестируем правильность расчета CRC."""
        Fixture = namedtuple('Fixture', ['data', 'crc'])
        fixtures = [
            Fixture(data=b'', crc=b'\x00\x00'),
            Fixture(data=b'\00', crc=b'\x00\x00'),
            Fixture(data=b'\01', crc=b'\x8f\x57'),
            Fixture(data=b'\xff', crc=b'\x18\x2a'),
            Fixture(data=b'\x01\xff', crc=b'\xbf\x03'),
            Fixture(data=b'\x01\xff\xa0', crc=b'\x44\x7b'),
            Fixture(data=b'DFJJKNKLF1&WLKEFFNEKRJFNKEJRN', crc=b'\x71\xbe'),
        ]
        for fixture in fixtures:
            with self.subTest(data=fixture.data):
                call = OwenCI8(addr=0, addr_len=8).calc_owen_crc(fixture.data)
                self.assertEqual(fixture.crc, call, msg='Неверный CRC!')

    def test_get_command_packet(self):
        """Тестируем правильность формирования пакета команды."""
        Fixture = namedtuple('Fixture', ['addr', 'addr_len', 'data', 'expected_packet'])
        fixtures = [
            # запрос DCNT
            Fixture(
                addr=0x02,
                addr_len=8,
                data=b'\xc1\x73',
                expected_packet=b'\x02\x10\xc1\x73\xe7\x1a',
            ),
            # запрос DSPD
            Fixture(
                addr=0x0F,
                addr_len=8,
                data=b'\x8f\xc2',
                expected_packet=b'\x0f\x10\x8f\xc2\x13\x56',
            ),
            # запрос DTMR
            Fixture(
                addr=0x0A,
                addr_len=8,
                data=b'\xe6\x9c',
                expected_packet=b'\x0a\x10\xe6\x9c\x85\x63',
            ),
            # запрос DCNT
            Fixture(
                addr=0x00,
                addr_len=11,
                data=b'\xc1\x73',
                expected_packet=b'\x00\x10\xc1\x73\x92\xe6',
            ),
            # запрос DSPD
            Fixture(
                addr=0x7FF,
                addr_len=11,
                data=b'\x8f\xc2',
                expected_packet=b'\xff\xf0\x8f\xc2\x02\x71',
            ),
            # запрос DTMR
            Fixture(
                addr=0x222,
                addr_len=11,
                data=b'\xe6\x9c',
                expected_packet=b'\x44\x50\xe6\x9c\xde\x15',
            ),
        ]
        for fixture in fixtures:
            with self.subTest(
                addr=fixture.addr, addr_len=fixture.addr_len, data=fixture.data
            ):
                call = OwenCI8(
                    addr=fixture.addr, addr_len=fixture.addr_len
                ).get_command_packet(parameter_hash=fixture.data)
                self.assertEqual(
                    fixture.expected_packet, call, 'Сформирован неверный пакет!'
                )

    def test_get_command_packet_with_invalid_parameter_len(self):
        """Тестируем поднятие ValueError, когда len(parameter) != 2."""
        invalid_parameters = [b'', b'\x00', b'abc', b'aaaaaaaa']
        for invalid_parameter in invalid_parameters:
            with (
                self.subTest(parameter=invalid_parameter),
                self.assertRaises(
                    ValueError,
                    msg='Исключение ValueError не поднято:',
                ),
            ):
                OwenCI8(addr=1, addr_len=8).get_command_packet(
                    parameter=invalid_parameter,
                )

    def test_bin_to_ascii(self):
        """Тестируем преобразование двоичного пакета в ASCII пакет."""
        Fixture = namedtuple('Fixture', ['bin', 'ascii'])
        fixtures = [
            Fixture(bin=b'', ascii=b'\x23\x0d'),
            Fixture(bin=b'\x0e', ascii=b'\x23\x47\x55\x0d'),
            # запрос DCNT
            Fixture(bin=b'\x05\x10\xc1\x73\x43\xe0', ascii=b'#GLHGSHNJKJUG\r'),
        ]
        for fixture in fixtures:
            with self.subTest(data=fixture.bin):
                call = OwenCI8(addr=1, addr_len=8).bin_to_ascii(
                    data=bytearray(fixture.bin)
                )
                self.assertEqual(
                    fixture.ascii, call, 'Bin пакет неверно преобразован в ASCII!'
                )

    def test_ascii_to_bin(self):
        """Тестируем преобразование валидного ASCII пакета в двоичный."""
        Fixture = namedtuple('Fixture', ['ascii', 'bin'])
        fixtures = [
            Fixture(
                ascii=b'#GHIJKLMNOPQRSTUV\r', bin=b'\x01\x23\x45\x67\x89\xab\xcd\xef'
            ),
            Fixture(
                ascii=b'#VUTSRQPONMLKJIHG\r', bin=b'\xfe\xdc\xba\x98\x76\x54\x32\x10'
            ),
            Fixture(
                ascii=b'#GHGKOVSIGGGVVGVVHUUHOOKKKKPP\r',
                bin=b'\x01\x04\x8f\xc2\x00\x0f\xf0\xff\x1e\xe1\x88\x44\x44\x99',
            ),
            Fixture(ascii=b'#GLHGSHNJKJUG\r', bin=b'\x05\x10\xc1\x73\x43\xe0'),
        ]
        for fixture in fixtures:
            with self.subTest(data=fixture.bin):
                call = OwenCI8(addr=1, addr_len=8).ascii_to_bin(data=fixture.ascii)
                self.assertEqual(fixture.bin, call, 'ASCII пакет неверно распакован!')

    def test_ascii_to_bin_rise_exception_with_invalid_packet_header(self):
        """Тестируем поднятие исключения, при невалидном заголовке пакета."""
        fixtures = [
            b'GGHIJKLMNOPQRSTUV\r',
            b'$GHIJKLMNOPQRSTUV\r',
            b'\x00GHIJKLMNOPQRSTUV\r',
        ]
        for fixture in fixtures:
            with (
                self.subTest(data=fixture),
                self.assertRaises(
                    PacketHeaderError,
                    msg='Исключение не поднято!',
                ),
            ):
                OwenCI8(addr=1, addr_len=8).ascii_to_bin(data=fixture)

    def test_ascii_to_bin_rise_exception_with_invalid_packet_footer(self):
        """Тестируем поднятие исключения, при невалидном окончании пакета."""
        fixtures = [
            b'#GHIJKLMNOPQRSTUV\n',
            b'#GHIJKLMNOPQRSTUVG',
            b'#GHIJKLMNOPQRSTUV\x00',
        ]
        for fixture in fixtures:
            with (
                self.subTest(data=fixture),
                self.assertRaises(
                    PacketHeaderError,
                    msg='Исключение не поднято!',
                ),
            ):
                OwenCI8(addr=1, addr_len=8).ascii_to_bin(data=fixture)

    def test_ascii_to_bin_rise_exception_with_invalid_packet_body(self):
        """Тестируем поднятие исключения, при невалидном теле пакета."""
        fixtures = [
            b'#GGGGGGGGGGH\r',
            b'#GGGGGGGGGF\r',
            b'#FGGGGGGGGG\r',
            b'#GGGGWGGGGG\r',
            b'#GGGGGGGGGGW\r',
        ]
        for fixture in fixtures:
            with (
                self.subTest(data=fixture),
                self.assertRaises(
                    PacketDecodeError,
                    msg='Исключение не поднято!',
                ),
            ):
                OwenCI8(addr=1, addr_len=8).ascii_to_bin(data=fixture)

    def test_check_bin_packet(self):
        """Тестируем возврат корректного блока данных с валидными пакетами."""
        Fixture = namedtuple(
            'Fixture', ['addr', 'addr_len', 'packet', 'hash', 'data_block']
        )
        fixtures = [
            Fixture(
                addr=0x02,
                addr_len=8,
                packet=b'\x02\x00\xc1\x73\xd5\x5f',
                hash=b'\xc1\x73',
                data_block=b'',
            ),
            Fixture(
                addr=0x555,
                addr_len=11,
                packet=b'\xaa\xa0\x8f\xc2\xcd\xa9',
                hash=b'\x8f\xc2',
                data_block=b'',
            ),
            Fixture(
                addr=0x555,
                addr_len=11,
                packet=b'\xaa\xa1\xe6\x9c\x00\x73\x25',
                hash=b'\xe6\x9c',
                data_block=b'\x00',
            ),
            Fixture(
                addr=0x00,
                addr_len=11,
                packet=b'\x00\x01\xc1\x73\xff\x53\x31',
                hash=b'\xc1\x73',
                data_block=b'\xff',
            ),
            Fixture(
                addr=0x00,
                addr_len=8,
                packet=b'\x00\x0f\x01\x23\x45\x67\x89\xab\xcd\xef'
                b'\x0f\xf0\x85\x43\x0c\x0d\x0e\xe3\x3b',
                hash=b'\x01\x23',
                data_block=b'\x45\x67\x89\xab\xcd\xef\x0f\xf0\x85\x43\x0c\x0d\x0e',
            ),
        ]
        for fixture in fixtures:
            with self.subTest(packet=fixture.packet):
                call = OwenCI8(
                    addr=fixture.addr, addr_len=fixture.addr_len
                ).check_bin_packet(
                    data=bytearray(fixture.packet), parameter_hash=fixture.hash
                )
                self.assertEqual(fixture.data_block, call)


class TestDataConverters(unittest.TestCase):
    def test_bcd_to_int_with_valid_data(self):
        """Тестируем преобразование BCD -> int."""
        Fixture = namedtuple('Fixture', ['data', 'expected_value'])
        fixtures = [
            Fixture(data=b'\x00', expected_value=0),
            Fixture(data=b'\x99', expected_value=99),
            Fixture(data=b'\x09', expected_value=9),
            Fixture(data=b'\x50', expected_value=50),
            Fixture(data=b'\x01', expected_value=1),
            Fixture(data=b'\x10', expected_value=10),
            Fixture(data=b'\x03\x04', expected_value=304),
            Fixture(data=b'\x12\x34\x56\x78\x90', expected_value=1234567890),
            Fixture(data=b'\x09\x87\x65\x43\x21', expected_value=987654321),
            Fixture(data=bytearray(b'\x09\x87\x65\x43\x21'), expected_value=987654321),
        ]
        for fixture in fixtures:
            with self.subTest(data=fixture.data):
                call = DataConverters.bcd_to_int(data=fixture.data)
                self.assertEqual(
                    fixture.expected_value, call, 'Значение преобразовано неверно!'
                )

    def test_bcd_to_int_rise_exception_on_invalid_dat(self):
        """Поднятие исключения при получении недопустимых значений."""
        invalid_values = [b'', b'\x0a', b'\xa0', b'\xaa', b'\xb1', b'\xff']
        for invalid_value in invalid_values:
            with (
                self.subTest(data=invalid_value),
                self.assertRaises(
                    BCDValueError,
                    msg='Исключение не поднято!',
                ),
            ):
                DataConverters.bcd_to_int(data=invalid_value)

    def test_clk_to_timedelta_with_valid_data(self):
        """Тестируем преобразование валидных данных."""
        Fixture = namedtuple('Fixture', ['data', 'expected_value'])
        fixtures = [
            Fixture(data=b'\x00\x00\x00\x00\x00\x00\x40', expected_value=timedelta()),
            Fixture(
                data=b'\x00\x00\x01\x00\x00\x00\x40', expected_value=timedelta(hours=1)
            ),
            Fixture(
                data=b'\x00\x00\x10\x02\x03\x05\x40',
                expected_value=timedelta(
                    hours=10, minutes=2, seconds=3, milliseconds=50
                ),
            ),
            Fixture(
                data=b'\x12\x34\x56\x32\x48\x57\x40',
                expected_value=timedelta(
                    hours=123456, minutes=32, seconds=48, milliseconds=570
                ),
            ),
        ]
        for fixture in fixtures:
            with self.subTest(data=fixture.data):
                call = DataConverters.clk_to_timedelta(data=fixture.data)
                self.assertEqual(fixture.expected_value, call)


if __name__ == '__main__':
    unittest.main()
