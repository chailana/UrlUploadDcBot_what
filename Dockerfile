FROM python:3.10.5-slim-buster

WORKDIR .
COPY . .

RUN pip3 install -r requirements.txt

CMD ["bash", "start.sh"]

