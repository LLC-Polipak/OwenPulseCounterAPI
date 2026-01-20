FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY ./requirements.txt /code/
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY . /code/app
CMD ["uvicorn", "app.main:application", "--host", "0.0.0.0", "--port", "8000"]
