# Bitflow92 Python Server

This repository hosts the Flask server for Bitflow92 projects.

Current features:

- Device Data receiver
- INA219 Solar Meter receiver
- OTA firmware updates
- Firmware dashboard

## Deployment

```bash
./deploy.sh
```

## Service

```bash
sudo systemctl restart flaskapp.service
```

## Logs

```bash
sudo journalctl -u flaskapp.service -f
```
