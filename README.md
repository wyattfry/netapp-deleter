# Azure NetApp Account Deleter

Ever wanted to delete a NetApp Account? Ever got that "nested resource" error? Then this program is for you. It deletes all NetApp accounts in your current Azure Subscription, starting with the most deeply nested resources (backups), then the next-deepest (vaults), then the NetApp account, then its resource group. It works on up to five accounts in parallel at a time (can be changed in the code).

## Install

Requires Python and an authenticated Azure CLI.

```
github clone https://github.com/wyattfry/netapp-deleter
cd netapp-deleter
python3 -m venv ./venv
source ./venv/bin/activate
pip install -f requirements.txt
```

## Run

```
./app.py
```

## Usage

```
usage: app.py [-h] [-y] [-v] [-w WORKERS]

Delete NetApp accounts and their resources

options:
  -h, --help            show this help message and exit
  -y, --yes             Skip confirmation prompt
  -v, --verbose         Enable verbose logging
  -w, --workers WORKERS
                        The max number of concurrent works to allow
```
