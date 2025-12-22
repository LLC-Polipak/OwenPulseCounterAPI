import asyncio
import logging

from fastapi import FastAPI, status
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import settings
from app.owen_poller.exeptions import DeviceNotFound
from app.owen_poller.owen_poller import SensorsPoller
from app.owen_poller.sender import PcsPerMinSender
from app.services.sensor_probe import SensorProbeService

logger = logging.getLogger(__name__)
application = FastAPI()

application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

poller = SensorsPoller()
if settings.poller_active:
    readings_sender = PcsPerMinSender(poller)


@application.on_event('startup')
async def app_startup():
    asyncio.create_task(poller.poll())
    if settings.poller_active:
        logger.info('Starting active poller...')
        asyncio.create_task(readings_sender.send_readings())


@application.get("/")
async def root():
    return {"message": "Owen Pulse Counter API"}


@application.get("/sensors/")
async def get_list_sensor_readings(work_centers: str):
    work_centers = work_centers.split(',')
    logger.debug(f"Getting readings for {work_centers}")
    response = poller.get_list_readings(work_centers)
    logger.debug(f"{response=}")
    return response


@application.get("/sensors/{name}")
async def get_sensor_readings(name: str):
    try:
        logger.debug(f"Getting readings for {name}")
        return poller.get_sensor_readings(name)
    except DeviceNotFound as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=err.args[0])


@application.get("/test_sensor/{addr}")
async def test_sensor(addr: int):
    try:
        result = SensorProbeService.probe(addr=addr)
        
        return {
            "addr": result.addr,
            "value": result.value,
            "measured_at": result.measured_at,
            "status": result.status,
        }
    
    except RuntimeError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )
    
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


# @app.get("/counters")
# async def get_all_devices():
#     return {
#         dev: {param_names[param]: value for param, value in params.items()}
#         for dev, params in poller.get_all().items()
#     }
