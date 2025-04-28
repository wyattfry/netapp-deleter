#!/usr/bin/env python3

import os
import time
import argparse
import logging
import concurrent.futures
from azure.identity import DefaultAzureCredential
from azure.mgmt.netapp import NetAppManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError
from datetime import datetime
from azure.mgmt.resource.subscriptions import SubscriptionClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
RED = "\033[0;31m"
GRN = "\033[0;32m"
RST = "\033[0m"

def setup_logging(verbose):
    """Configure logging based on verbosity level"""
    if verbose:
        logger.setLevel(logging.DEBUG)
        # Enable Azure SDK debug logging
        logging.getLogger('azure').setLevel(logging.DEBUG)
        logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        # Silence Azure SDK debug logging
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
        logging.getLogger('azure.identity').setLevel(logging.WARNING)

def get_subscription_id():
    """Get the current subscription ID using Azure SDK"""
    try:
        credential = DefaultAzureCredential()
        subscription_client = SubscriptionClient(credential)
        
        # Get the first subscription (usually the default one)
        subscriptions = list(subscription_client.subscriptions.list())
        if not subscriptions:
            raise ValueError("No subscriptions found. Please ensure you have access to at least one subscription.")
        
        # If there's only one subscription, use it
        if len(subscriptions) == 1:
            return subscriptions[0].subscription_id
            
        # If there are multiple subscriptions, try to find the one marked as default
        for sub in subscriptions:
            if getattr(sub, 'is_default', False):
                return sub.subscription_id
                
        # If no default found, use the first one
        return subscriptions[0].subscription_id
        
    except Exception as e:
        raise ValueError(f"Failed to get subscription ID: {str(e)}")

def delete_netapp_resources(netapp_account_id):
    # Extract resource group name and account name from the NetApp account ID
    parts = netapp_account_id.split('/')
    resource_group_name = parts[4]
    netapp_account_name = parts[-1]
    
    try:
        # First, list and delete all volumes in the account
        logger.info(f"Deleting volumes in NetApp account '{netapp_account_name}'...")
        try:
            # List all pools in the account
            pools = netapp_client.pools.list(resource_group_name, netapp_account_name)
            for pool in pools:
                # List and delete all volumes in each pool
                volumes = netapp_client.volumes.list(resource_group_name, netapp_account_name, pool.name)
                for volume in volumes:
                    logger.info(f"  Deleting volume '{volume.name}' in pool '{pool.name}'...")
                    try:
                        poller = netapp_client.volumes.begin_delete(
                            resource_group_name, netapp_account_name, pool.name, volume.name
                        )
                        poller.result()  # Wait for deletion to complete
                        logger.info(f"{GRN}Successfully deleted volume '{volume.name}'{RST}")
                    except Exception as e:
                        logger.error(f"{RED}Error deleting volume '{volume.name}': {str(e)}{RST}")
                        raise  # Re-raise to trigger early termination
        except Exception as e:
            logger.error(f"{RED}Error listing/deleting volumes: {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

        # Delete backup vaults
        logger.info(f"Deleting backup vaults in NetApp account '{netapp_account_name}'...")
        try:
            # List backup vaults using the correct API
            backup_vaults = netapp_client.backup_vaults.list_by_net_app_account(resource_group_name, netapp_account_name)
            
            # Process each vault found
            for vault in backup_vaults:
                # Extract the actual vault name from the format "account_name/vault_name"
                vault_name = vault.name.split('/')[-1]
                logger.info(f"Processing backup vault '{vault_name}'...")
                
                try:
                    # First, list and delete all backups in the vault
                    logger.info(f"Listing backups in vault '{vault_name}'...")
                    backups = list(netapp_client.backups.list_by_vault(resource_group_name, netapp_account_name, vault_name))
                    
                    if backups:
                        logger.info(f"Found {len(backups)} backups to delete in vault '{vault_name}'")
                        for backup in backups:
                            backup_name = backup.name.split('/')[-1]
                            logger.info(f"Deleting backup '{backup_name}'...")
                            try:
                                poller = netapp_client.backups.begin_delete(
                                    resource_group_name, netapp_account_name, vault_name, backup_name
                                )
                                poller.result()  # Wait for deletion to complete
                                logger.info(f"{GRN}Successfully deleted backup '{backup_name}'{RST}")
                            except Exception as e:
                                logger.error(f"{RED}Error deleting backup '{backup_name}': {str(e)}{RST}")
                                raise  # Re-raise to trigger early termination
                    else:
                        logger.info(f"No backups found in vault '{vault_name}'")

                    # Now delete the vault itself
                    logger.info(f"Deleting backup vault '{vault_name}'...")
                    try:
                        poller = netapp_client.backup_vaults.begin_delete(
                            resource_group_name, netapp_account_name, vault_name
                        )
                        poller.result()  # Wait for deletion to complete
                        
                        # Verify the vault is actually deleted
                        try:
                            print(f"Verifying netapp has disassociated with the vault...")
                            netapp_client.backup_vaults.get(resource_group_name, netapp_account_name, vault_name)
                            logger.error(f"{RED}Backup vault '{vault_name}' still exists after deletion{RST}")
                            raise Exception(f"Backup vault '{vault_name}' deletion failed - resource still exists")
                        except ResourceNotFoundError:
                            logger.info(f"{GRN}Successfully deleted backup vault '{vault_name}'{RST}")
                    except Exception as e:
                        logger.error(f"{RED}Error deleting backup vault '{vault_name}': {str(e)}{RST}")
                        raise  # Re-raise to trigger early termination
                    
                except Exception as e:
                    logger.error(f"{RED}Error processing backup vault '{vault_name}': {str(e)}{RST}")
                    raise  # Re-raise to trigger early termination
                
        except Exception as e:
            logger.error(f"{RED}Error listing/deleting backup vaults: {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

        # Then delete the account itself
        logger.info(f"Deleting NetApp account '{netapp_account_name}'...")
        max_retries = 3
        retry_delay = 30  # seconds
        
        for attempt in range(max_retries):
            try:
                poller = netapp_client.accounts.begin_delete(
                    resource_group_name, netapp_account_name
                )
                poller.result()  # Wait for deletion to complete
                logger.info(f"{GRN}Successfully deleted NetApp account '{netapp_account_name}'{RST}")
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e)
                if "Cannot delete resource while nested resources exist" in error_str and attempt < max_retries - 1:
                    logger.info(f"Account deletion failed due to nested resources, waiting {retry_delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay)
                    continue
                logger.error(f"{RED}Error deleting NetApp account '{netapp_account_name}':{RST} {str(e)}")
                raise  # Re-raise to trigger early termination

        # Finally, delete the resource group if it's empty
        logger.info(f"Deleting resource group '{resource_group_name}'...")
        try:
            poller = resource_client.resource_groups.begin_delete(
                resource_group_name
            )
            poller.result()  # Wait for deletion to complete
            logger.info(f"{GRN}Successfully deleted resource group '{resource_group_name}'{RST}")
        except Exception as e:
            logger.error(f"{RED}Error deleting resource group '{resource_group_name}': {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

    except Exception as e:
        logger.error(f"{RED}Error processing NetApp account '{netapp_account_id}': {str(e)}{RST}")
        raise  # Re-raise to trigger early termination

def list_and_delete_netapp_accounts(skip_confirmation=False):
    logger.info("Fetching and deleting NetApp accounts...")
    try:
        # Get all NetApp accounts directly
        logger.info("Listing all NetApp accounts in subscription...")
        netapp_accounts = list(netapp_client.accounts.list_by_subscription())
        
        if not netapp_accounts:
            logger.info("No NetApp accounts found in subscription.")
            return

        logger.info(f"Found {len(netapp_accounts)} NetApp accounts to delete: {', '.join([x.name for x in netapp_accounts])}")        
        if not skip_confirmation:
            response = input(f"This will delete all {len(netapp_accounts)} NetApp accounts in your subscription. Are you sure you want to proceed? y/N: ")
            if response.lower() != 'y':
                logger.info("Operation cancelled by user.")
                return
        
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
                    logger.error(f"{RED}Failed to delete NetApp account {account.name}: {str(e)}{RST}")
                    # Cancel all pending futures
                    for f in future_to_account:
                        f.cancel()
                    raise  # Re-raise to trigger early termination

    except Exception as e:
        logger.error(f"{RED}Error in list_and_delete_netapp_accounts: {str(e)}{RST}")
        raise  # Re-raise to trigger early termination

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Delete NetApp accounts and their resources')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        # Unset REQUESTS_CA_BUNDLE environment variable
        if 'REQUESTS_CA_BUNDLE' in os.environ:
            del os.environ['REQUESTS_CA_BUNDLE']

        # Initialize credentials and clients
        credential = DefaultAzureCredential()
        subscription_id = get_subscription_id()
        netapp_client = NetAppManagementClient(credential, subscription_id)
        resource_client = ResourceManagementClient(credential, subscription_id)

        list_and_delete_netapp_accounts(skip_confirmation=args.yes)
    except Exception as e:
        logger.error(f"{RED}Script terminated due to error: {str(e)}{RST}")
        exit(1) 
