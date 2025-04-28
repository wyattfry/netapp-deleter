# Azure NetApp Account Deleter

![Python Checks](https://github.com/wyattfry/netapp-deleter/actions/workflows/python-checks.yml/badge.svg)

Ever wanted to delete a NetApp Account? Ever got that "nested resource" error? Then this program is for you. It deletes all NetApp accounts in your current Azure Subscription, starting with the most deeply nested resources (backups), then the next-deepest (vaults), then the NetApp account, then its resource group. It works on up to five accounts in parallel at a time (can be changed in the code).

## Install

Requires Python and an authenticated Azure CLI.

```bash
git clone https://github.com/wyattfry/netapp-deleter
cd netapp-deleter
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
./netapp_deleter_cli.py
```

## Usage

- `-y`: don't prompt, just delete them all
- `-v`: verbose mode
- `-w`: specify the maximum number of concurrent workers (default: 5)

## Project Structure

The project is organized into the following modules:

- `netapp_deleter/`: Main package directory
  - `__init__.py`: Package initialization
  - `app.py`: Main application logic
  - `azure_utils.py`: Azure client initialization and subscription handling
  - `logging_utils.py`: Logging configuration
  - `resource_deleter.py`: NetApp resource deletion logic
- `netapp_deleter_cli.py`: Command-line interface
- `test_app.py`: Test suite

