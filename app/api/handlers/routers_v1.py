"""Маршруты API версии 1 для работы с сенсорами."""

import logging
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_device_registry, get_sensor_poller
from app.owen_drivers.exceptions import ImproperlyConfiguredError
from app.owen_drivers.modbus_pvt110 import ModbusPVT110
from app.owen_drivers.owen_ci8 import OwenCI8
from app.owen_poller.exceptions import (
    DeviceAddressAlreadyExists,
    DeviceNameAlreadyExists,
    DeviceNotFound,
)
from app.owen_poller.formatters import CounterFormatter, EnvironmentFormatter
from app.owen_poller.sensor import Sensor

if TYPE_CHECKING:
    from app.owen_poller.device_registry import DeviceRegistry
    from app.owen_poller.poller import SensorsPoller

router = APIRouter()
logger = logging.getLogger(__name__)


class SensorCreateRequest(BaseModel):
    """Схема запроса на добавление нового сенсора в список опроса."""

    name: str = Field(..., min_length=1, description='Уникальное имя сенсора (РЦ)')
    driver: Literal['ci8', 'pvt110'] = Field(
        'ci8', description='Тип драйвера устройства (ci8 или pvt110)'
    )
    addr: int = Field(..., ge=0, description='Сетевой адрес устройства')
    addr_len: int = Field(8, description='Длина адреса для протокола ОВЕН (8 или 11)')
    parameter: Literal['DCNT', 'DSPD', 'DTMR'] | None = Field(
        'DCNT', description='Запрашиваемый параметр для счетчика СИ8'
    )
    watchdog_threshold: int | None = Field(
        None, ge=2, description='Порог срабатывания сторожевого таймера заморозки'
    )


@router.post('/sensors/', status_code=status.HTTP_201_CREATED, tags=['Sensors'])
async def add_sensor(
    payload: SensorCreateRequest,
    poller: 'SensorsPoller' = Depends(get_sensor_poller),
):
    """Добавить новый счетчик/сенсор в список опроса и сохранить локально."""
    raw_config = {
        'name': payload.name,
        'driver': 'OwenCI8' if payload.driver == 'ci8' else 'ModbusPVT110',
        'addr': payload.addr,
        'formatter': (
            'CounterFormatter'
            if payload.driver == 'ci8'
            else 'EnvironmentFormatter'
        ),
        'parameter': payload.parameter if payload.driver == 'ci8' else None,
        'watchdog_threshold': payload.watchdog_threshold,
    }
    if payload.driver == 'ci8':
        raw_config['addr_len'] = payload.addr_len

    try:
        sensor = poller.register_new_sensor(raw_config)
    except (DeviceAddressAlreadyExists, DeviceNameAlreadyExists) as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from None
    except (ImproperlyConfiguredError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from None

    return {
        'status': 'ok',
        'message': f'Устройство {sensor.name} (адрес {payload.addr}) успешно добавлено.',
    }


@router.get('/sensors/', tags=['Sensors'])
async def get_list_sensor_readings(
    work_centers: str, registry: 'DeviceRegistry' = Depends(get_device_registry)
):
    """Получить показания сенсоров по списку рабочих центров."""
    work_centers = work_centers.split(',')
    logger.debug(f'Getting readings for {work_centers}')
    response = registry.get_list_readings(work_centers)
    logger.debug(f'{response=}')
    return response


@router.get('/sensors/{name}', tags=['Sensors'])
async def get_sensor_readings(
    name: str, registry: 'DeviceRegistry' = Depends(get_device_registry)
):
    """Получить текущие показания одного сенсора по имени."""
    try:
        logger.debug(f'Getting readings for {name}')
        return registry.get_sensor_readings(name)
    except DeviceNotFound as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=err.args[0]
        ) from None


@router.get('/sensors/config/', tags=['Sensors'])
async def get_sensors_config(poller: 'SensorsPoller' = Depends(get_sensor_poller)):
    """Получить текущую конфигурацию всех активных сенсоров."""
    config_list = []

    for sensor in poller.registry.sensors.values():
        driver = sensor.device
        param = sensor.parameter
        if isinstance(param, bytes):
            param_repr = f'0x{param.hex()}'
        else:
            param_repr = str(param) if param is not None else None

        config_list.append(
            {
                'name': sensor.name,
                'driver': driver.__class__.__name__,
                'address': getattr(driver, 'raw_addr', driver.addr),
                'addr_len': getattr(driver, 'addr_len', None),
                'parameter': param_repr,
                'poll_priority': getattr(driver, 'poll_priority', None),
                'poll_interval_sec': getattr(driver, 'poll_interval', None),
            }
        )

    return config_list


@router.get('/test_sensor/{driver_name}/{addr}', tags=['Debug'])
async def test_sensor(
    driver_name: str, addr: int, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    """Проверить работоспособность сенсора, отсутствующего в конфигурации."""
    drivers_map = {'ci8': OwenCI8, 'pvt110': ModbusPVT110}
    formatters_map = {'ci8': CounterFormatter, 'pvt110': EnvironmentFormatter}

    driver_name = driver_name.lower()
    if driver_name not in drivers_map:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'Неизвестный драйвер. Доступны: {list(drivers_map.keys())}',
        )

    device_class = drivers_map[driver_name]
    formatter_class = formatters_map[driver_name]

    temp_sensor = Sensor(
        name=f'debug_{driver_name}_{addr}',
        device=device_class(addr=addr),
        formatter=formatter_class(),
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


@router.post('/sensors/{name}/reboot', tags=['Device Management'])
async def api_reboot_device(
    name: str, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    """Выполнить аппаратную перезагрузку сенсора (не поддерживает СИ8)."""
    if name not in poller.registry.sensors:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f'Сенсор {name} не найден в реестре.'
        )

    sensor = poller.registry.sensors[name]

    if not poller.connection.connect():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            'COM-порт недоступен, невозможно отправить команду.',
        )

    success = sensor.device.reboot(poller.connection.provider)

    if not success:
        return {
            'status': 'error',
            'message': f'Прибор {name} не ответил, либо не поддерживает перезагрузку.',
        }

    return {
        'status': 'ok',
        'message': f'Команда на перезагрузку отправлена на прибор {name}.',
    }


@router.get('/sensors/{name}/hardware-status', tags=['Device Management'])
async def api_get_hardware_status(
    name: str, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    """Вернуть аппаратный статус устройства (не поддерживает СИ8)."""
    if name not in poller.registry.sensors:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f'Сенсор {name} не найден.')

    sensor = poller.registry.sensors[name]

    if not poller.connection.connect():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'COM-порт недоступен.')

    hw_status = sensor.device.read_device_status(poller.connection.provider)

    if hw_status is None:
        return {
            'status': 'not_supported',
            'description': 'Прибор не поддерживает чтение статуса или не на связи.',
        }

    return {'status': 'ok', 'hardware_details': hw_status}
