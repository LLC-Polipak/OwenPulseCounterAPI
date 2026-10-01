from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from app.owen_poller.device_registry import DeviceRegistry
    from app.owen_poller.poller import SensorsPoller


async def get_sensor_poller(request: Request) -> 'SensorsPoller':
    return request.app.state.sensor_poller


async def get_device_registry(request: Request) -> 'DeviceRegistry':
    return request.app.state.sensor_poller.registry
