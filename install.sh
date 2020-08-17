#!/bin/bash

# must run under root to avoid local user inst
sudo pip install -r requirements.txt
sudo pip3 install -r requirements.txt

sudo cp metering.service /etc/systemd/system/metering.service
sudo cp control.service /etc/systemd/system/control.service
sudo cp webapp.service /etc/systemd/system/webapp.service

sudo systemctl daemon-reload

sudo systemctl start metering
sudo systemctl enable metering

sudo systemctl start control
sudo systemctl enable control

sudo systemctl start webapp
sudo systemctl enable webapp

# old stuff
# sharing logs directory with web/apache
#sudo apt install apache2 -y
#cd /var/www/html
#sudo ln -s /var/metering
# if ! [ -f index-deb.html ]; then  # first time install if original file backup missing
#   sudo mv index.html index-deb.html
#   sudo ln -s /opt/metering/index.html
# fi
