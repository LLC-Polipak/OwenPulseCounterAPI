import asyncio
import copy
import logging

import requests
from requests import JSONDecodeError, RequestException

from app.api.config import configure_logging, settings
from app.owen_poller.owen_poller import SensorReading

configure_logging()
logger = logging.getLogger(__name__)


class PcsPerMinSender:
    def __init__(self, poller):
        self.poller = poller
        self.last_readings = {}

    async def send_readings(self):
        while True:
            for_sent = []
            for sensor in self.poller.sensors.values():
                current_reading: SensorReading = sensor.reading
                logger.debug(f'Reading sensor {sensor.name}: {current_reading.value}')
                if current_reading.value is None:
                    continue
                previous_reading: SensorReading = self.last_readings.get(sensor.name)
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
                for_sent.append(
                    {
                        'sensor': sensor.name,
                        'value': speed,
                        # 'measured_at': current_reading.time.
                    }
                )
                self.last_readings[sensor.name] = copy.copy(current_reading)
            logger.debug(f'{for_sent=}')
            if for_sent:
                try:
                    logger.info('Отправка данных в PhyHub..')
                    response = requests.post(
                        url=settings.receiver_url,
                        headers={'Authorization': f'Token {settings.receiver_token}'},
                        json=for_sent,
                        timeout=settings.poller_connection_timeout,
                    )
                    logger.info(response.json())
                except (RequestException, JSONDecodeError) as err:
                    logger.error(f'Ошибка отправки:\n{err}')
            await asyncio.sleep(30)
