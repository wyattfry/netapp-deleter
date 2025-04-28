#!/usr/bin/env python3

import os
import time
import concurrent.futures
from azure.identity import DefaultAzureCredential
from azure.mgmt.netapp import NetAppManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError
from datetime import datetime

RED = "\033[0;31m"
GRN = "\033[0;32m"
RST = "\033[0m"

# Unset REQUESTS_CA_BUNDLE environment variable
if 'REQUESTS_CA_BUNDLE' in os.environ:
    del os.environ['REQUESTS_CA_BUNDLE']

# Initialize credentials
credential = DefaultAzureCredential()

# Subscription ID - replace with your actual subscription ID
# subscription_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'

# Initialize clients
netapp_client = NetAppManagementClient(credential, subscription_id)
resource_client = ResourceManagementClient(credential, subscription_id)

def delete_netapp_resources(netapp_account_id):
    # Extract resource group name and account name from the NetApp account ID
    parts = netapp_account_id.split('/')
    resource_group_name = parts[4]
    netapp_account_name = parts[-1]
    
    try:
        # First, list and delete all volumes in the account
        print(f"[DEBUG]  Deleting volumes in NetApp account '{netapp_account_name}'...")
        try:
            # List all pools in the account
            pools = netapp_client.pools.list(resource_group_name, netapp_account_name)
            for pool in pools:
                # List and delete all volumes in each pool
                volumes = netapp_client.volumes.list(resource_group_name, netapp_account_name, pool.name)
                for volume in volumes:
                    print(f"[DEBUG]  Deleting volume '{volume.name}' in pool '{pool.name}'...")
                    try:
                        poller = netapp_client.volumes.begin_delete(
                            resource_group_name, netapp_account_name, pool.name, volume.name
                        )
                        poller.result()  # Wait for deletion to complete
                        print(f"{GRN}[INFO]  Successfully deleted volume '{volume.name}'{RST}")
                    except Exception as e:
                        print(f"{RED}[ERROR]  Error deleting volume '{volume.name}': {str(e)}{RST}")
                        raise  # Re-raise to trigger early termination
        except Exception as e:
            print(f"{RED}[ERROR]  Error listing/deleting volumes: {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

        # Delete backup vaults
        print(f"[DEBUG]  Deleting backup vaults in NetApp account '{netapp_account_name}'...")
        try:
            # List backup vaults using the correct API
            backup_vaults = netapp_client.backup_vaults.list_by_net_app_account(resource_group_name, netapp_account_name)
            
            # Process each vault found
            for vault in backup_vaults:
                # Extract the actual vault name from the format "account_name/vault_name"
                vault_name = vault.name.split('/')[-1]
                print(f"[DEBUG]  Processing backup vault '{vault_name}'...")
                
                try:
                    # First, list and delete all backups in the vault
                    print(f"[DEBUG]  Listing backups in vault '{vault_name}'...")
                    backups = list(netapp_client.backups.list_by_vault(resource_group_name, netapp_account_name, vault_name))
                    
                    if backups:
                        print(f"[DEBUG]  Found {len(backups)} backups to delete in vault '{vault_name}'")
                        for backup in backups:
                            backup_name = backup.name.split('/')[-1]
                            print(f"[DEBUG]  Deleting backup '{backup_name}'...")
                            try:
                                poller = netapp_client.backups.begin_delete(
                                    resource_group_name, netapp_account_name, vault_name, backup_name
                                )
                                poller.result()  # Wait for deletion to complete
                                print(f"{GRN}[INFO]  Successfully deleted backup '{backup_name}'{RST}")
                            except Exception as e:
                                print(f"{RED}[ERROR]  Error deleting backup '{backup_name}': {str(e)}{RST}")
                                raise  # Re-raise to trigger early termination
                    else:
                        print(f"[INFO]  No backups found in vault '{vault_name}'")

                    # Now delete the vault itself
                    print(f"[INFO]  Deleting backup vault '{vault_name}'...")
                    try:
                        poller = netapp_client.backup_vaults.begin_delete(
                            resource_group_name, netapp_account_name, vault_name
                        )
                        poller.result()  # Wait for deletion to complete
                        
                        try:
                            print(f"[DEBUG]  Verifying netapp has disassociated with the vault...")
                            netapp_client.backup_vaults.get(resource_group_name, netapp_account_name, vault_name)
                            print(f"{RED}[ERROR]  Backup vault '{vault_name}' still exists after deletion{RST}")
                            raise Exception(f"Backup vault '{vault_name}' deletion failed - resource still exists")
                        except ResourceNotFoundError:
                            print(f"{GRN}[INFO]  Successfully deleted backup vault '{vault_name}'{RST}")
                    except Exception as e:
                        print(f"{RED}[ERROR]  Error deleting backup vault '{vault_name}': {str(e)}{RST}")
                        raise  # Re-raise to trigger early termination
                    
                except Exception as e:
                    print(f"{RED}[ERROR]  Error processing backup vault '{vault_name}': {str(e)}{RST}")
                    raise  # Re-raise to trigger early termination
                
        except Exception as e:
            print(f"{RED}[ERROR]  Error listing/deleting backup vaults: {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

        # Then delete the account itself
        print(f"[DEBUG]  Deleting NetApp account '{netapp_account_name}'...")
        max_retries = 3
        retry_delay = 30  # seconds
        
        for attempt in range(max_retries):
            try:
                poller = netapp_client.accounts.begin_delete(
                    resource_group_name, netapp_account_name
                )
                poller.result()  # Wait for deletion to complete
                print(f"{GRN}[INFO]  Successfully deleted NetApp account '{netapp_account_name}'{RST}")
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e)
                if "Cannot delete resource while nested resources exist" in error_str and attempt < max_retries - 1:
                    print(f"[INFO]  Account deletion failed due to nested resources, waiting {retry_delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay)
                    continue
                print(f"{RED}[ERROR]  Error deleting NetApp account '{netapp_account_name}':{RST} {str(e)}")
                raise  # Re-raise to trigger early termination

        # Finally, delete the resource group if it's empty
        print(f"[DEBUG]  Deleting resource group '{resource_group_name}'...")
        try:
            poller = resource_client.resource_groups.begin_delete(
                resource_group_name
            )
            poller.result()  # Wait for deletion to complete
            print(f"{GRN}[INFO]  Successfully deleted resource group '{resource_group_name}'{RST}")
        except Exception as e:
            print(f"{RED}[ERROR]  Error deleting resource group '{resource_group_name}': {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

    except Exception as e:
        print(f"{RED}[ERROR]  Error processing NetApp account '{netapp_account_id}': {str(e)}{RST}")
        raise  # Re-raise to trigger early termination

def list_and_delete_netapp_accounts():
    print("[DEBUG]  Fetching and deleting NetApp accounts...")
    try:
        # Get all NetApp accounts directly
        print("[DEBUG]  Listing all NetApp accounts in subscription...")
        netapp_accounts = list(netapp_client.accounts.list_by_subscription())
        
        if not netapp_accounts:
            print("[DEBUG]  No NetApp accounts found in subscription.")
            return

        print(f"[DEBUG]  Found {len(netapp_accounts)} NetApp accounts to delete.")
        
        # Delete accounts in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_account = {
                executor.submit(delete_netapp_resources, account.id): account 
                for account in netapp_accounts
            }
            
            for future in concurrent.futures.as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    future.result()  # This will raise any exceptions that occurred
                except Exception as e:
                    print(f"{RED}[ERROR]  Failed to delete NetApp account {account.name}: {str(e)}{RST}")
                    # Cancel all pending futures
                    for f in future_to_account:
                        f.cancel()
                    raise  # Re-raise to trigger early termination

    except Exception as e:
        print(f"{RED}[ERROR]  Error in list_and_delete_netapp_accounts: {str(e)}{RST}")
        raise  # Re-raise to trigger early termination

if __name__ == "__main__":
    try:
        list_and_delete_netapp_accounts()
    except Exception as e:
        print(f"{RED}[ERROR]  Script terminated due to error: {str(e)}{RST}")
        exit(1)

