#!/bin/bash

# Restart the service
sudo systemctl restart ezeml.service

# Append the current datetime to restarts.txt
echo "$(date '+%Y-%m-%d %H:%M:%S') ezeml.service restarted" >> /home/pasta/ezeml/restarts.log
