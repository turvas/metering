#!/bin/bash

# must run under root to avoid local user inst
echo Installing Python Requirements..
sudo pip install -r requirements.txt
sudo pip3 install -r requirements.txt

echo Copying service unit files..
sudo cp metering.service /etc/systemd/system/metering.service
sudo cp control.service /etc/systemd/system/control.service
sudo cp webapp.service /etc/systemd/system/webapp.service

echo Starting services..
sudo systemctl daemon-reload

sudo systemctl start metering
sudo systemctl start control
sudo systemctl start webapp

echo Enabling services at startup..
sudo systemctl enable metering
sudo systemctl enable control
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
echo Complete
