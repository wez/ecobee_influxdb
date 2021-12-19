#!/usr/bin/python3

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import datetime
import requests
import logging
import json
import sys
from time import sleep
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("ecobee")

with open(Path.home() / ".ecobee_influx_config.json") as f:
    CONFIG = json.load(f)


def to_bool(value):
    valid = {"true": True, "t": True, "1": True, "false": False, "f": False, "0": False}

    if isinstance(value, bool):
        return value

    lower_value = value.lower()
    if lower_value in valid:
        return valid[lower_value]
    else:
        raise ValueError('invalid literal for boolean: "%s"' % value)


def api_request(url, method, headers=""):
    if method == "post":
        # post to url
        return requests.post(url).json()
    if method == "get":
        # get method
        return requests.get(url, headers=headers).json()


def get_access_token():
    LOG.info("Refreshing access token")
    token_file = Path.home() / ".ecobee_refresh_token"
    with open(token_file) as f:
        refreshToken = f.readline().strip()

    token_url = (
        "https://api.ecobee.com/token?grant_type=refresh_token&code="
        + refreshToken
        + "&client_id="
        + CONFIG["ecobee_api_key"]
    )
    r = api_request(token_url, "post")

    access_token = r["access_token"]
    new_refresh_token = r["refresh_token"]

    with open(token_file, "w") as f:
        f.write(new_refresh_token)

    LOG.debug("old refresh token = " + refreshToken)
    LOG.debug("access token = " + access_token)
    LOG.debug("new refresh token = " + new_refresh_token)

    return access_token


def logPoint(
    sensorName=None,
    thermostatName=None,
    sensorValue=None,
    sensorType=None,
    recordedTime=None,
):
    point = (
        influxdb_client.Point(sensorType)
        .tag("thermostat_name", thermostatName)
        .tag("sensor", sensorName)
        .field("value", sensorValue)
    )
    if recordedTime:
        return point.time(recordedTime)
    return point


def get_thermostat_data(access_token):
    payload = json.dumps(
        {
            "selection": {
                "selectionType": "registered",
                "selectionMatch": "",
                "includeRuntime": True,
                "includeEquipmentStatus": True,
                "includeWeather": True,
                "includeSensors": True,
                "includeExtendedRuntime": True,
                "includeDevice": True,
                "includeEvents": True,
                "includeProgram": True,
            }
        }
    )
    url = "https://api.ecobee.com/1/thermostat?format=json&body=" + payload
    headers = {"content-type": "text/json", "Authorization": "Bearer " + access_token}
    return api_request(url, "get", headers)


def thermostat_data_to_points(tdata):
    points = []

    for thermostat in tdata["thermostatList"]:
        thermostatName = thermostat["name"]
        sensors = thermostat["remoteSensors"]
        current_weather = thermostat["weather"]["forecasts"][0]
        current_program = thermostat["program"]["currentClimateRef"]
        if len(thermostat["events"]) > 0:
            current_program = thermostat["events"][0]["name"]

        for sensor in sensors:
            for capability in sensor["capability"]:
                if capability["type"] == "occupancy":
                    value = to_bool(capability["value"])
                    points.append(
                        logPoint(
                            sensorName=sensor["name"],
                            thermostatName=thermostatName,
                            sensorValue=value,
                            sensorType="occupancy",
                        )
                    )
                if capability["type"] == "temperature":
                    if str.isdigit(capability["value"]) > 0:
                        temp = float(capability["value"]) / 10.0
                    else:
                        temp = 0.0
                    points.append(
                        logPoint(
                            sensorName=sensor["name"],
                            thermostatName=thermostatName,
                            sensorValue=temp,
                            sensorType="temp",
                        )
                    )
                if capability["type"] == "humidity":
                    points.append(
                        logPoint(
                            sensorName=sensor["name"],
                            thermostatName=thermostatName,
                            sensorValue=float(capability["value"]),
                            sensorType="humidity",
                        )
                    )

        ext_runtime = thermostat["extendedRuntime"]
        # This is a good candidate for visualizing with the Mosaic type
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=ext_runtime["hvacMode"][2],
                sensorType="hvacMode",
                recordedTime=ext_runtime["lastReadingTimestamp"],
            )
        )

        runtime = thermostat["runtime"]
        temp = float(runtime["actualTemperature"]) / 10.0
        heatTemp = float(runtime["desiredHeat"]) / 10.0
        coolTemp = float(runtime["desiredCool"]) / 10.0
        outside_temp = current_weather["temperature"] / 10
        outside_wind = current_weather["windSpeed"]
        outside_humidity = current_weather["relativeHumidity"]
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=temp,
                sensorType="actualTemperature",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(runtime["actualHumidity"]),
                sensorType="actualHumidity",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(heatTemp),
                sensorType="desiredHeat",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(coolTemp),
                sensorType="desiredCool",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(outside_temp),
                sensorType="outsideTemp",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(outside_wind),
                sensorType="outsideWind",
            )
        )
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=float(outside_humidity),
                sensorType="outsideHumidity",
            )
        )
        # This is a good candidate for visualizing with the Mosaic type
        points.append(
            logPoint(
                sensorName=thermostatName,
                thermostatName=thermostatName,
                sensorValue=str(current_program),
                sensorType="currentProgram",
            )
        )
    LOG.debug(f"recording {len(points)} points for thermostat data")
    return points


def logDurationPoint(
    sensorName=None, sensorValue=None, sensorType=None, recordedTime=None
):
    return (
        influxdb_client.Point(sensorType)
        .tag("sensor", sensorName)
        .field("value", sensorValue)
        .time(recordedTime)
    )


def get_runtime_data(tdata, delta):
    points = []
    end_date = datetime.datetime.today()
    start_date = end_date - delta
    for thermostat in tdata["thermostatList"]:
        thermostatName = thermostat["name"]

        payload = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "columns": "auxHeat1,compCool1,fan,outdoorTemp,zoneAveTemp",
            "selection": {
                "selectionType": "thermostats",
                "selectionMatch": thermostat["identifier"],
            },
        }

        payload = json.dumps(payload)

        url = "https://api.ecobee.com/1/runtimeReport?format=json&body=" + payload
        headers = {
            "content-type": "text/json",
            "Authorization": "Bearer " + access_token,
        }
        data = api_request(url, "get", headers)

        for row in data["reportList"][0]["rowList"]:
            fields = row.strip().split(",")
            myday, mytime, auxHeat1, compCool1, fan, outdoorTemp, zoneAveTemp = fields
            date_str = myday + " " + mytime
            datetime_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            if datetime_obj < start_date:
                continue

            builttime = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")

            if auxHeat1 != "":
                points.append(
                    logDurationPoint(
                        sensorName=thermostatName,
                        sensorValue=float(auxHeat1),
                        sensorType="heattime",
                        recordedTime=builttime,
                    )
                )
            if compCool1 != "":
                points.append(
                    logDurationPoint(
                        sensorName=thermostatName,
                        sensorValue=float(compCool1),
                        sensorType="cooltime",
                        recordedTime=builttime,
                    )
                )
            if fan != "":
                points.append(
                    logDurationPoint(
                        sensorName=thermostatName,
                        sensorValue=float(fan),
                        sensorType="fantime",
                        recordedTime=builttime,
                    )
                )
    LOG.debug(f"recording {len(points)} points for runtime duration")
    return points


LOG.info("starting loop")
# Look back to the prior day when doing the first pull of
# runtime data
delta = datetime.timedelta(days=1)
queries = 0
access_token = None

while True:
    client = influxdb_client.InfluxDBClient(
        url=CONFIG["influxdb_server"],
        token=CONFIG["influxdb_token"],
        org=CONFIG["influxdb_org"],
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    if (access_token is None) or queries > 45:
        access_token = get_access_token()
        queries = 0
    else:
        queries += 1

    tdata = get_thermostat_data(access_token)

    write_api.write(
        bucket=CONFIG["influxdb_bucket"], record=thermostat_data_to_points(tdata)
    )
    write_api.write(
        bucket=CONFIG["influxdb_bucket"], record=get_runtime_data(tdata, delta)
    )

    # After we've done at least one get_runtime_data, adjust the delta
    # to just the past hour to avoid an excessive number of updates
    delta = datetime.timedelta(hours=1)

    sleep(60)
