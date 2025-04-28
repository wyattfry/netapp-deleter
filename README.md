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

## Options

- `-y`: don't prompt, just delete them all
- `-v`: verbose mode
