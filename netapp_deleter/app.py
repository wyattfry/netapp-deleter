"""
Main application module for the NetApp deleter.
"""

import os
import concurrent.futures
from .logging_utils import logger, RED, setup_logging
from .azure_utils import get_azure_clients
from .resource_deleter import delete_netapp_resources


def list_and_delete_netapp_accounts(netapp_client, resource_client, skip_confirmation: bool, max_workers: int):
    """
    List and delete all NetApp accounts in the current subscription.
    
    Args:
        netapp_client: The NetApp management client
        resource_client: The resource management client
        skip_confirmation: Whether to skip the confirmation prompt
        max_workers: Maximum number of concurrent workers
    """
    logger.info("Fetching and deleting NetApp accounts...")
    try:
        # Get all NetApp accounts directly
        logger.info("Listing all NetApp accounts in subscription...")
        netapp_accounts = list(netapp_client.accounts.list_by_subscription())

        if not netapp_accounts:
            logger.info("No NetApp accounts found in subscription.")
            return

        logger.info(
            f"Found {len(netapp_accounts)} NetApp accounts to delete: {', '.join([x.name for x in netapp_accounts])}"
        )
        if not skip_confirmation:
            response = input(
                f"This will delete all {len(netapp_accounts)} NetApp accounts in your subscription. Are you sure you want to proceed? y/N: "
            )
            if response.lower() != "y":
                logger.info("Operation cancelled by user.")
                return

        # Delete accounts in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_account = {
                executor.submit(delete_netapp_resources, netapp_client, resource_client, account.id): account
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


def main():
    """Main entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Delete NetApp accounts and their resources")
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt", default=False
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging", default=False
    )
    parser.add_argument(
        "-w", "--workers", type=int, help="The max number of concurrent workers to allow", default=5
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        # Unset REQUESTS_CA_BUNDLE environment variable
        if "REQUESTS_CA_BUNDLE" in os.environ:
            del os.environ["REQUESTS_CA_BUNDLE"]

        # Initialize credentials and clients
        netapp_client, resource_client = get_azure_clients()

        list_and_delete_netapp_accounts(netapp_client, resource_client, args.yes, args.workers)
    except Exception as e:
        logger.error(f"{RED}Script terminated due to error: {str(e)}{RST}")
        exit(1)


if __name__ == "__main__":
    main() 