"""
Azure utilities for the NetApp deleter.
"""

from azure.identity import DefaultAzureCredential
from azure.mgmt.netapp import NetAppManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from .logging_utils import logger


def get_subscription_id():
    """Get the current subscription ID using Azure SDK"""
    try:
        credential = DefaultAzureCredential()
        subscription_client = SubscriptionClient(credential)

        # Get the first subscription (usually the default one)
        subscriptions = list(subscription_client.subscriptions.list())
        if not subscriptions:
            raise ValueError(
                "No subscriptions found. Please ensure you have access to at least one subscription."
            )

        # If there's only one subscription, use it
        if len(subscriptions) == 1:
            return subscriptions[0].subscription_id

        # If there are multiple subscriptions, try to find the one marked as default
        for sub in subscriptions:
            if getattr(sub, "is_default", False):
                return sub.subscription_id

        # If no default found, use the first one
        return subscriptions[0].subscription_id

    except Exception as e:
        raise ValueError(f"Failed to get subscription ID: {str(e)}")


def get_azure_clients():
    """Initialize and return Azure clients"""
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id()
    netapp_client = NetAppManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)
    return netapp_client, resource_client 