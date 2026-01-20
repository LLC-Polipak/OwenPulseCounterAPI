from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def root():
    return {'message': 'Owen Pulse Counter API'}


@router.get('/health')
async def health_check():
    return {'status': 'healthy', 'message': 'Service is running'}
