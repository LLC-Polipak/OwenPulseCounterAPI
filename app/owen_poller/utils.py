from datetime import datetime

from app.owen_poller.state import SensorMinuteSnapshot, SensorRuntimeState

OFFLINE_THRESHOLD = 60
MIN_SUCCESS_RATE = 0.5

def calc_rate(state: SensorRuntimeState) -> float:
    if state.attempt_count == 0:
        return 0.0
    return round(state.success_count / state.attempt_count, 3)

def calc_status(state, diff, *, now, is_sensor=False) -> str:
    if state.last_success_ts is None or (
            now - state.last_success_ts).total_seconds() > OFFLINE_THRESHOLD:
        return 'OFFLINE'

    if calc_rate(state) < MIN_SUCCESS_RATE:
        return 'UNKNOWN'

    if is_sensor:
        return 'OK' if diff is not None else 'UNKNOWN'

    if diff == 0:
        return 'STOP'
    return 'OK'

def finalize_previous_minute(state: SensorRuntimeState, sensor):
    from app.owen_counter.modbus_pvt110 import ModbusPVT110

    is_pvt = isinstance(sensor.device, ModbusPVT110)

    if is_pvt:
        diff = state.last_value
    else:
        if state.minute_start_value is not None and state.minute_end_value is not None:
            if state.minute_end_value >= state.minute_start_value:
                diff = state.minute_end_value - state.minute_start_value
            else:
                diff = (sensor.device.MAX_VALUE - state.minute_start_value + state.minute_end_value)
        else:
            diff = None

    now = datetime.now()
    state.last_minute_snapshot = SensorMinuteSnapshot(
        minute=state.current_minute,
        value=diff,
        success_rate=calc_rate(state),
        status=calc_status(state, diff, now=now, is_sensor=is_pvt),
        last_seen_at=state.last_success_ts,
    )

def start_new_minute(state: SensorRuntimeState, minute: datetime) -> None:
    state.current_minute = minute
    state.minute_start_value = None
    state.minute_end_value = None
    state.success_count = 0
    state.attempt_count = 0