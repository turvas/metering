#!/bin/bash

pip install schedule requests

sudo cp metering.service /etc/systemd/system/metering.service
sudo systemctl start metering
sudo systemctl enable metering

sudo cp control.service /etc/systemd/system/control.service
sudo systemctl start control
sudo systemctl enable control