import asyncio
import copy
import logging

import requests
from requests import JSONDecodeError, RequestException

from app.api.config import config, configure_logging

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

            for sensor in self.poller.registry.sensors.values():
                current_reading = sensor.reading
                if current_reading.value is None:
                    continue

                previous_reading = self.last_readings.get(sensor.name)

                if previous_reading is None or previous_reading.value is None:
                    duration = 0.0
                    prev_val = current_reading.value
                    self.last_readings[sensor.name] = copy.copy(current_reading)
                else:
                    duration = (
                        current_reading.time - previous_reading.time
                    ).total_seconds()
                    prev_val = previous_reading.value

                if duration <= 0 and previous_reading is not None:
                    duration = 0.0
                    prev_val = current_reading.value

                metric = sensor.device.calculate_instant_metric(
                    curr_val=current_reading.value,
                    prev_val=prev_val,
                    duration_sec=duration,
                )

                payload = sensor.formatter.format_telemetry(sensor.name, metric)
                for_sent.append(payload)

                if duration > 0:
                    self.last_readings[sensor.name] = copy.copy(current_reading)

            if for_sent:
                try:
                    logger.info(f'Отправка {len(for_sent)} записей в PhyHub..')
                    requests.post(
                        url=config.receiver_url,
                        headers={'Authorization': f'Token {config.receiver_token}'},
                        json=for_sent,
                        timeout=config.poller_connection_timeout,
                    )
                except (RequestException, JSONDecodeError) as err:
                    logger.error(f'Ошибка отправки на сервер:\n{err}')

            await asyncio.sleep(30)
