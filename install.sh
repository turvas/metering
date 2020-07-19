#!/bin/bash

pip install schedule requests

sudo cp metering.service /etc/systemd/system/metering.service
sudo systemctl start metering
sudo systemctl enable metering

sudo cp control.service /etc/systemd/system/control.service
sudo systemctl start control
sudo systemctl enable control

# sharing logs directory with web/apache
sudo apt install apache2 -y
cd /var/www/html
sudo ln -s /var/metering
sudo mv index.html index-deb.html
sudo ln -s /opt/metering/index.html
