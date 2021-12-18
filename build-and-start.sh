#!/bin/sh
sudo docker build -t ecobee-influx .
sudo docker-compose up -d
