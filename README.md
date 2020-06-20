# metering script for raspberry pi

reading from gpio 3
requires schedule python module, 
```bash
pip install schedule
```

for service to run 
```bash
sudo cp metering.service /etc/systemd/system/metering.service
sudo systemctl start metering
sudo systemctl enable metering
```
