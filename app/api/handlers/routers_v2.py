import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.dependencies import get_device_registry

if TYPE_CHECKING:
    from owen_poller.device_registry import DeviceRegistry


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/sensors/', tags=['Sensors'])
async def get_list_sensor_readings(
    work_centers: str, registry: 'DeviceRegistry' = Depends(get_device_registry)
):
    """
    Получить полные показания сенсора по списку рабочих центров.

    Возвращает метрику, статус сенсора, текущее значение и процент успешных
    опросов сенсора в течение минуты.
    """
    work_centers = work_centers.split(',')
    response = registry.get_minute_state(work_centers)
    return response
