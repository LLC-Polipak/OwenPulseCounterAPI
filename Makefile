.PHONY: test lint lint-fix format format-check ruff-all

# Показать все проблемы (без изменений)
lint:
	ruff check .

# Показать проблемы + что МОЖЕТ быть автоисправлено
lint-preview:
	ruff check . --show-fixes

# Автоматически исправить всё возможное
lint-fix:
	ruff check . --fix

# Проверка форматирования (без изменений)
format-check:
	ruff format . --check

# Отформатировать код
format:
	ruff format .

# Всё сразу: автофиксы + форматирование
ruff-all:
	ruff format .
	ruff check . --fix
