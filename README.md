# metering script for raspberry pi

reading from gpio 3
requires schedule python module, 
  pip install schedule
  
fr service to run 
  sudo cp metering.service /etc/systemd/system/metering.service
  sudo systemctl start metering
  sudo systemctl enable metering
