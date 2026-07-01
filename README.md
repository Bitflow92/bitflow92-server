# Bitflow92 Server

Central Flask server for Bitflow92 IoT projects.

## Purpose

This repository hosts the production Flask server running on
**bitflow92.co.za**.

Current supported systems:

-   FIDL Device Data
-   INA219 Solar Meter
-   OTA Firmware Updates
-   ESP32 Firmware Dashboard

------------------------------------------------------------------------

# Repository Workflow

**GitHub is the source of truth.**

    Codex
      │
      ▼
    Create Feature Branch
      │
      ▼
    Open Pull Request
      │
      ▼
    Review Pull Request
      │
      ▼
    Merge into main
      │
      ▼
    SSH to VPS
      │
      ▼
    cd ~/python_server
      │
      ▼
    ./deploy_main.sh
      │
      ▼
    Production Updated

------------------------------------------------------------------------

# Deployment Procedure

## Step 1 -- Review Pull Request

Review all changes created by Codex.

If satisfied, merge the Pull Request into the **main** branch on GitHub.

**Never deploy directly from a feature branch.**

## Step 2 -- Connect to the VPS

``` bash
ssh cdr2bok297@bitflow92.co.za
```

## Step 3 -- Navigate to the project

``` bash
cd ~/python_server
```

## Step 4 -- Deploy

``` bash
./deploy_main.sh
```

The deployment script should:

1.  Checkout `main`
2.  Fetch the latest code
3.  Synchronise with `origin/main`
4.  Install/update Python packages
5.  Restart `flaskapp.service`
6.  Display the service status

## Step 5 -- Verify

Check:

-   Home page
-   Device Data
-   INA219 Solar Meter
-   OTA Dashboard

------------------------------------------------------------------------

# Useful Commands

## View Flask logs

``` bash
sudo journalctl -u flaskapp.service -f
```

## Restart Flask

``` bash
sudo systemctl restart flaskapp.service
```

## Service Status

``` bash
sudo systemctl status flaskapp.service
```

## Git Status

``` bash
git status
```

## Fetch Latest

``` bash
git fetch origin
```

## Current Branch

``` bash
git branch
```

------------------------------------------------------------------------

# Repository Structure

    python_server/
    ├── server.py
    ├── deploy_main.sh
    ├── update_dashboard.py
    ├── requirements.txt
    ├── README.md
    ├── firmware_dashboard/
    ├── ota/
    └── venv/

------------------------------------------------------------------------

# Production Rules

-   GitHub is the source of truth.
-   Deploy from **main** only.
-   Development happens through feature branches and Pull Requests.
-   Runtime files are not committed to Git.
-   Do not edit production code directly on the VPS.

------------------------------------------------------------------------

# Future Enhancements

-   Rollback script
-   Branch deployment script
-   Database storage
-   Historical graphs
-   Multi-device support

