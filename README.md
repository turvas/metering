# metering and control scripts for raspberry pi

## metering
reading from gpio 3,

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

## control

requires schedule and requests python module,
```bash
pip install schedule requests
```

for service to run
```bash
sudo cp control.service /etc/systemd/system/control.service
sudo systemctl start control
sudo systemctl enable control
```

