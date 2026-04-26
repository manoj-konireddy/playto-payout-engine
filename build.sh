#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python backend/manage.py migrate
python backend/manage.py seed_data
python backend/manage.py collectstatic --noinput
