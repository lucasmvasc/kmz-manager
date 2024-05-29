#!/bin/bash
source /home/ubuntu/kmz_manager/venv/bin/activate
exec gunicorn -w 3 -b unix:/home/ubuntu/kmz_manager/kmz_manager.sock app:app
