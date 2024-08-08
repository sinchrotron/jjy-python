FROM python:3.10
ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /app
RUN apt update && apt -y install portaudio19-dev python3-pyaudio
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python","jjy_original.py"]