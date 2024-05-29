#!/bin/bash
source /home/ubuntu/kmz-manager/venv/bin/activate
exec gunicorn -w 3 -b unix:/home/ubuntu/kmz-manager/kmz_manager.sock app:app
