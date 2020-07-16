# metering and control scripts for raspberry pi
to install everything run
```bash
chmod +x install.sh
./install.sh
```
or can install both components separatley as described below

## metering
multiple meters can be connected to several gpio pins, described in "meters" list

requires python module "schedule", 
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
multiple relays can be connected to several gpio pins, described in "relays" list

requires python modules: schedule and requests,
```bash
pip install schedule requests
```

for service to run
```bash
sudo cp control.service /etc/systemd/system/control.service
sudo systemctl start control
sudo systemctl enable control
```

