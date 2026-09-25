from datetime import datetime

from app.owen_poller.state import SensorMinuteSnapshot, SensorRuntimeState

OFFLINE_THRESHOLD = 60
MIN_SUCCESS_RATE = 0.5


def calc_rate(state: SensorRuntimeState) -> float:
    """Вычисляет процент успешных опросов (от 0.0 до 1.0)."""
    if state.attempt_count == 0:
        return 0.0
    return round(state.success_count / state.attempt_count, 3)


def calc_status(state, diff, *, now, is_cumulative=True) -> str:
    """
    Рассчитывает логический статус прибора (ОК, Остановлен, Неизвестен, Отключен).

    :param state: Текущее состояние (SensorRuntimeState).
    :param diff: Вычисленная разница показаний (для счетчиков) или само значение.
    :param now: Текущее время.
    :param is_cumulative: Флаг накопительного прибора.
    :return: Строка со статусом.
    """
    if (
        state.last_success_ts is None
        or (now - state.last_success_ts).total_seconds() > OFFLINE_THRESHOLD
    ):
        return 'OFFLINE'

    if calc_rate(state) < MIN_SUCCESS_RATE:
        return 'UNKNOWN'

    if not is_cumulative:
        return 'OK' if diff is not None else 'UNKNOWN'

    if diff == 0:
        return 'STOP'
    return 'OK'


def finalize_previous_minute(state: SensorRuntimeState, sensor):
    """
    Завершает текущую минуту опроса, вычисляет финальный Diff (или берет значение)
    и сохраняет результат в last_minute_snapshot.

    :param state: Мутируемое состояние сенсора.
    :param sensor: Объект логического сенсора (содержит ссылку на драйвер).
    """
    if not sensor.device.is_cumulative:
        diff = state.last_value
    else:
        if state.minute_start_value is not None and state.minute_end_value is not None:
            if state.minute_end_value >= state.minute_start_value:
                diff = state.minute_end_value - state.minute_start_value
            else:
                diff = (
                    sensor.device.MAX_VALUE
                    - state.minute_start_value
                    + state.minute_end_value
                )
        else:
            diff = None

    now = datetime.now()
    state.last_minute_snapshot = SensorMinuteSnapshot(
        minute=state.current_minute,
        value=diff,
        success_rate=calc_rate(state),
        status=calc_status(
            state, diff, now=now, is_cumulative=sensor.device.is_cumulative
        ),
        last_seen_at=state.last_success_ts,
    )


def start_new_minute(state: SensorRuntimeState, minute: datetime) -> None:
    """Сбрасывает минутные счетчики (успешности, начальных значений) для новой минуты."""
    state.current_minute = minute
    state.minute_start_value = None
    state.minute_end_value = None
    state.success_count = 0
    state.attempt_count = 0
