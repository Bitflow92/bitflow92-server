#!/bin/bash

set -e

APP_DIR="/home/cdr2bok297/python_server"
SERVICE="flaskapp.service"

echo ""
echo "Updating repository..."

cd "$APP_DIR"

git pull origin main

echo ""
echo "Updating Python packages..."

source venv/bin/activate

pip install -r requirements.txt

deactivate

echo ""
echo "Restarting Flask..."

sudo systemctl restart $SERVICE

echo ""
echo "Status"

sudo systemctl status $SERVICE --no-pager
