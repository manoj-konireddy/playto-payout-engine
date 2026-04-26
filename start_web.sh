#!/usr/bin/env bash
set -o errexit

gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
