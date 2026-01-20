from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from app.owen_poller.owen_poller import SensorsPoller


async def get_sensor_poller(request: Request) -> 'SensorsPoller':
    return request.app.state.sensor_poller
