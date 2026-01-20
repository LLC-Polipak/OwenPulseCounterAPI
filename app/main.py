import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import settings
from app.api.config import config
from app.api.handlers.health_check import router as health_check_router
from app.api.handlers.routers_v1 import router as routers_v1
from app.api.handlers.routers_v2 import router as routers_v2
from app.owen_poller.owen_poller import SensorsPoller
from app.owen_poller.sender import PcsPerMinSender

logger = logging.getLogger(__name__)

poller = SensorsPoller(settings)

if config.poller_active:
    readings_sender = PcsPerMinSender(poller)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sensor_poller = poller

    poller_task = asyncio.create_task(poller.poll())
    if config.poller_active:
        logger.info('Starting active poller...')
        asyncio.create_task(readings_sender.send_readings())

    yield

    poller.stop()
    poller_task.cancel()
    try:
        await asyncio.wait_for(poller_task, timeout=2)
    except asyncio.CancelledError:
        logger.info('Poller stopped cleanly')
    except asyncio.TimeoutError:
        logger.critical('Poller did not stop in time')


application = FastAPI(
    lifespan=lifespan,
)

application.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

application.include_router(health_check_router)
application.include_router(routers_v1)
application.include_router(routers_v2, prefix='/api/v2')

# @application.on_event('startup')
# async def app_startup():
#     asyncio.create_task(poller.poll())
#     if settings.poller_active:
#         logger.info('Starting active poller...')
#         asyncio.create_task(readings_sender.send_readings())
