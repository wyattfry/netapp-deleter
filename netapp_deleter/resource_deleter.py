"""
NetApp resource deletion logic.
"""

import time
from azure.core.exceptions import ResourceNotFoundError
from .logging_utils import logger, RED, GRN, RST


def delete_netapp_resources(netapp_client, resource_client, netapp_account_id):
    """
    Delete all resources associated with a NetApp account.
    
    Args:
        netapp_client: The NetApp management client
        resource_client: The resource management client
        netapp_account_id: The ID of the NetApp account to delete
    """
    # Extract resource group name and account name from the NetApp account ID
    parts = netapp_account_id.split("/")
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
                volumes = netapp_client.volumes.list(
                    resource_group_name, netapp_account_name, pool.name
                )
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
            backup_vaults = netapp_client.backup_vaults.list_by_net_app_account(
                resource_group_name, netapp_account_name
            )

            # Process each vault found
            for vault in backup_vaults:
                # Extract the actual vault name from the format "account_name/vault_name"
                vault_name = vault.name.split("/")[-1]
                logger.info(f"Processing backup vault '{vault_name}'...")

                try:
                    # First, list and delete all backups in the vault
                    logger.info(f"Listing backups in vault '{vault_name}'...")
                    backups = list(
                        netapp_client.backups.list_by_vault(
                            resource_group_name, netapp_account_name, vault_name
                        )
                    )

                    if backups:
                        logger.info(f"Found {len(backups)} backups to delete in vault '{vault_name}'")
                        for backup in backups:
                            backup_name = backup.name.split("/")[-1]
                            logger.info(f"Deleting backup '{backup_name}'...")
                            try:
                                poller = netapp_client.backups.begin_delete(
                                    resource_group_name,
                                    netapp_account_name,
                                    vault_name,
                                    backup_name,
                                )
                                poller.result()  # Wait for deletion to complete
                                logger.info(f"{GRN}Successfully deleted backup '{backup_name}'{RST}")
                            except Exception as e:
                                logger.error(
                                    f"{RED}Error deleting backup '{backup_name}': {str(e)}{RST}"
                                )
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
                            netapp_client.backup_vaults.get(
                                resource_group_name, netapp_account_name, vault_name
                            )
                            logger.error(
                                f"{RED}Backup vault '{vault_name}' still exists after deletion{RST}"
                            )
                            raise Exception(
                                f"Backup vault '{vault_name}' deletion failed - resource still exists"
                            )
                        except ResourceNotFoundError:
                            logger.info(f"{GRN}Successfully deleted backup vault '{vault_name}'{RST}")
                    except Exception as e:
                        logger.error(
                            f"{RED}Error deleting backup vault '{vault_name}': {str(e)}{RST}"
                        )
                        raise  # Re-raise to trigger early termination

                except Exception as e:
                    logger.error(
                        f"{RED}Error processing backup vault '{vault_name}': {str(e)}{RST}"
                    )
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
                if (
                    "Cannot delete resource while nested resources exist" in error_str
                    and attempt < max_retries - 1
                ):
                    logger.info(
                        f"Account deletion failed due to nested resources, waiting {retry_delay} seconds before retry {attempt + 1}/{max_retries}..."
                    )
                    time.sleep(retry_delay)
                    continue
                logger.error(
                    f"{RED}Error deleting NetApp account '{netapp_account_name}':{RST} {str(e)}"
                )
                raise  # Re-raise to trigger early termination

        # Finally, delete the resource group if it's empty
        logger.info(f"Deleting resource group '{resource_group_name}'...")
        try:
            poller = resource_client.resource_groups.begin_delete(resource_group_name)
            poller.result()  # Wait for deletion to complete
            logger.info(f"{GRN}Successfully deleted resource group '{resource_group_name}'{RST}")
        except Exception as e:
            logger.error(f"{RED}Error deleting resource group '{resource_group_name}': {str(e)}{RST}")
            raise  # Re-raise to trigger early termination

    except Exception as e:
        logger.error(f"{RED}Error processing NetApp account '{netapp_account_id}': {str(e)}{RST}")
        raise  # Re-raise to trigger early termination 