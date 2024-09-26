FROM python:3.11.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y

COPY requirements.txt .

RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

COPY . .