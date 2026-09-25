import asyncio
import copy
import logging

import requests
from requests import JSONDecodeError, RequestException

from app.api.config import config, configure_logging
from app.owen_poller.owen_poller import SensorReading

configure_logging()
logger = logging.getLogger(__name__)


class PcsPerMinSender:
    """
    Фоновая задача для периодической отправки собранных данных на внешний сервер (PhyHub).
    Самостоятельно обрабатывает разницу между накопительными и мгновенными сенсорами.
    """

    def __init__(self, poller):
        """
        :param poller: Ссылка на инстанс SensorsPoller для доступа к данным сенсоров.
        """
        self.poller = poller
        self.last_readings = {}

    async def send_readings(self):
        """
        Бесконечный цикл формирования JSON payload'а и отправки его по HTTP.
        Вызывается раз в 30 секунд.
        """
        while True:
            for_sent = []
            for sensor in self.poller.sensors.values():
                current_reading: SensorReading = sensor.reading
                if current_reading.value is None:
                    continue

                if not sensor.device.is_cumulative:
                    val_to_send = current_reading.value
                else:
                    previous_reading = self.last_readings.get(sensor.name)
                    if previous_reading is None or previous_reading.value is None:
                        self.last_readings[sensor.name] = copy.copy(current_reading)
                        continue

                    duration = current_reading.time - previous_reading.time
                    if duration.total_seconds() <= 0:
                        continue

                    speed = (
                        (current_reading.value - previous_reading.value)
                        / duration.total_seconds()
                        * 60
                    )
                    val_to_send = speed

                payload = {'sensor': sensor.name}

                if isinstance(val_to_send, dict):
                    payload.update(val_to_send)
                else:
                    payload['value'] = val_to_send

                for_sent.append(payload)
                self.last_readings[sensor.name] = copy.copy(current_reading)

            if for_sent:
                try:
                    logger.info('Отправка данных в PhyHub..')
                    requests.post(
                        url=config.receiver_url,
                        headers={'Authorization': f'Token {config.receiver_token}'},
                        json=for_sent,
                        timeout=config.poller_connection_timeout,
                    )
                except (RequestException, JSONDecodeError) as err:
                    logger.error(f'Ошибка отправки:\n{err}')

            await asyncio.sleep(30)
