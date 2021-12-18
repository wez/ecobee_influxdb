FROM python:latest
WORKDIR /app
COPY ./* /app/
RUN pip install -r requirements.txt
CMD [ "python3", "-u", "ecobee_influxdb.py" ]
