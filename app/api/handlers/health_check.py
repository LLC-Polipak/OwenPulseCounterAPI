"""Маршруты для проверки состояния сервиса."""

from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def root():
    """Получить информацию о сервисе."""
    return {'message': 'Owen Pulse Counter API'}


@router.get('/health')
async def health_check():
    """Вернуть статус работы сервиса."""
    return {'status': 'healthy', 'message': 'Service is running'}
