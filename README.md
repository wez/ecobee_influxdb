# ecobee_influxdb

A script to pull data from the Ecobee API and write to influxDB 2.x.
useful for making visualizations with Grafana, etc.

# Setup

* Start by visting https://www.ecobee.com/home/developer/api/examples/ex1.shtml
* Follow the instructions to generate an API key, authorize the app with a PIN, and finally get a "refresh code"
* The refresh code needs to be written as a single line to the file `~/.ecobee_refresh_token`
* Create a config file named `.ecobee_influx_config.json`:

```json
{
  "ecobee_api_key": "<copy this from your ecobee developer section>",
  "influxdb_server": "http://192.168.1.4:8086",
  "influxdb_bucket": "YourBucketName",
  "influxdb_org": "YourOrgName",
  "influxdb_token": "YourInfluxToken"
}
```

# Docker

If you want to run this in docker, instead of putting those config files in your home directory,
you can place them in a directory named `state` and then run `build-and-start.sh`.

