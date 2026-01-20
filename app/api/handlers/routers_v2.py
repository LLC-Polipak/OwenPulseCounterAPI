import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.dependencies import get_sensor_poller

if TYPE_CHECKING:
    from app.owen_poller.owen_poller import SensorsPoller

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/sensors/')
async def get_list_sensor_readings(
    work_centers: str, poller: 'SensorsPoller' = Depends(get_sensor_poller)
):
    work_centers = work_centers.split(',')
    response = poller.get_minute_state(work_centers)
    return response
