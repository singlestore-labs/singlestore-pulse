# Dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip3 install git+https://github.com/singlestore-labs/singlestore-pulse.git@aanshu/sessionID

COPY main.py .
COPY .env .

EXPOSE 8000

CMD ["python", "main.py"]
