#!/bin/bash
source /home/ubuntu/kmz-manager/venv/bin/activate
exec gunicorn -w 3 -b 127.0.0.1:5000 app:app
