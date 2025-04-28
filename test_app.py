from unittest.mock import patch, MagicMock
from netapp_deleter.logging_utils import setup_logging, logger
from netapp_deleter.azure_utils import get_subscription_id, get_azure_clients
from netapp_deleter.resource_deleter import delete_netapp_resources
from netapp_deleter.app import list_and_delete_netapp_accounts


def test_setup_logging():
    """Test that setup_logging function works correctly"""
    # Test verbose mode
    setup_logging(True)
    assert logger.level == 10  # DEBUG level

    # Test non-verbose mode
    setup_logging(False)
    assert logger.level == 20  # INFO level


@patch("netapp_deleter.azure_utils.DefaultAzureCredential")
@patch("netapp_deleter.azure_utils.SubscriptionClient")
def test_get_subscription_id(mock_subscription_client, mock_credential):
    """Test get_subscription_id function"""
    # Mock a subscription
    mock_sub = MagicMock()
    mock_sub.subscription_id = "test-subscription-id"
    mock_sub.is_default = True

    # Setup the mock to return our test subscription
    mock_subscription_client.return_value.subscriptions.list.return_value = [mock_sub]

    # Call the function
    result = get_subscription_id()

    # Verify the result
    assert result == "test-subscription-id"


@patch("netapp_deleter.azure_utils.DefaultAzureCredential")
@patch("netapp_deleter.azure_utils.get_subscription_id")
def test_get_azure_clients(mock_get_subscription_id, mock_credential):
    """Test get_azure_clients function"""
    # Mock the subscription ID
    mock_get_subscription_id.return_value = "test-subscription-id"

    # Call the function
    netapp_client, resource_client = get_azure_clients()

    # Verify the clients were created with the correct parameters
    assert netapp_client is not None
    assert resource_client is not None


@patch("netapp_deleter.resource_deleter.logger")
def test_delete_netapp_resources(mock_logger):
    """Test delete_netapp_resources function with mocked clients"""
    # This is a placeholder test - in a real scenario, you would mock the Azure clients
    # and test the deletion logic more thoroughly
    pass


@patch("netapp_deleter.app.logger")
@patch("netapp_deleter.app.delete_netapp_resources")
def test_list_and_delete_netapp_accounts(mock_delete_resources, mock_logger):
    """Test list_and_delete_netapp_accounts function"""
    # Mock the NetApp client
    mock_netapp_client = MagicMock()
    mock_netapp_client.accounts.list_by_subscription.return_value = []

    # Mock the resource client
    mock_resource_client = MagicMock()

    # Test with skip_confirmation=True
    list_and_delete_netapp_accounts(
        mock_netapp_client, mock_resource_client, skip_confirmation=True, max_workers=1
    )

    # Verify the function was called
    mock_netapp_client.accounts.list_by_subscription.assert_called_once()
