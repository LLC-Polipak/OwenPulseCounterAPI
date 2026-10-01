import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException

from app.dependencies import get_device_registry, get_sensor_poller
from app.owen_drivers.modbus_pvt110 import ModbusPVT110
from app.owen_drivers.owen_ci8 import OwenCI8
from app.owen_poller.exceptions import DeviceNotFound
from app.owen_poller.sensor import Sensor

if TYPE_CHECKING:
    from app.owen_poller.device_registry import DeviceRegistry
    from app.owen_poller.poller import SensorsPoller

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/sensors/', tags=['Sensors'])
async def get_list_sensor_readings(
    work_centers: str, registry: 'DeviceRegistry' = Depends(get_device_registry)
):
    work_centers = work_centers.split(',')
    logger.debug(f'Getting readings for {work_centers}')
    response = registry.get_list_readings(work_centers)
    logger.debug(f'{response=}')
    return response


@router.get('/sensors/{name}', tags=['Sensors'])
async def get_sensor_readings(
    name: str, registry: 'DeviceRegistry' = Depends(get_device_registry)
):
    try:
        logger.debug(f'Getting readings for {name}')
        return registry.get_sensor_readings(name)
    except DeviceNotFound as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=err.args[0]
        ) from None


@router.get('/sensors/config/', tags=['Sensors'])
async def get_sensors_config(registry: 'DeviceRegistry' = Depends(get_device_registry)):
    config_list = []
    for sensor in registry.get_sorted_sensors():
        config_list.append(
            {
                'name': sensor.name,
                'driver': sensor.device.__class__.__name__,
                'address': sensor.device.addr,
                'poll_priority': sensor.device.poll_priority,
                'poll_interval_sec': sensor.device.poll_interval,
            }
        )
    return config_list


@router.get('/test_sensor/{driver_name}/{addr}', tags=['Debug'])
async def test_sensor(
    driver_name: str, addr: int, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    drivers_map = {'ci8': OwenCI8, 'pvt110': ModbusPVT110}

    driver_name = driver_name.lower()
    if driver_name not in drivers_map:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'Неизвестный драйвер. Доступны: {list(drivers_map.keys())}',
        )

    device_class = drivers_map[driver_name]

    temp_sensor = Sensor(
        name=f'debug_{driver_name}_{addr}',
        device=device_class(addr=addr),
        provider=poller.connection.provider,
        parameter=OwenCI8.DCNT if driver_name == 'ci8' else None,
    )

    if not temp_sensor.update():
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            'Устройство не ответило (Таймаут или ошибка CRC)',
        )

    result = temp_sensor.get()
    return {
        'driver': driver_name,
        'addr': addr,
        'value': result.get('reading'),
        'measured_at': result.get('reading_time'),
    }
