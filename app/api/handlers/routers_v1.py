import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException

from app.dependencies import get_sensor_poller
from app.owen_poller.exeptions import DeviceNotFound

if TYPE_CHECKING:
    from app.owen_poller.owen_poller import SensorsPoller

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/sensors/')
async def get_list_sensor_readings(
    work_centers: str, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    work_centers = work_centers.split(',')
    logger.debug(f'Getting readings for {work_centers}')
    response = poller.get_list_readings(work_centers)
    logger.debug(f'{response=}')
    return response


@router.get('/sensors/{name}')
async def get_sensor_readings(
    name: str, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    try:
        logger.debug(f'Getting readings for {name}')
        return poller.get_sensor_readings(name)
    except DeviceNotFound as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=err.args[0]
        ) from None


@router.get('/test_sensor/{addr}')
async def test_sensor(addr: int, poller: 'SensorsPoller' = Depends(get_sensor_poller)):
    sensor = poller.test_sensor_by_addr(addr)
    sensor.update()
    result = sensor.get()

    return {
        'addr': addr,
        'value': result.get('reading'),
        'measured_at': result.get('reading_time'),
    }
