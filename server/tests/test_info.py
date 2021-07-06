import pytest
import requests
from http import HTTPStatus
from unittest.mock import Mock, patch

import server
from error import assert_error


@pytest.fixture
def client():
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@patch('info.requests.get')
def test_get_info_successfuly(mock_get_info, client):
    mock_get_info.return_value = Mock()
    mock_get_info.return_value.status_code = HTTPStatus.OK

    SAMPLE_INFO = {
        "id":
        "0317109ca2848f061e27dbf497ec47243d7aea6",
        "alias":
        "VIOLETSCAN",
        "color":
        "031710",
        "num_peers":
        0,
        "num_pending_channels":
        0,
        "num_active_channels":
        0,
        "num_inactive_channels":
        0,
        "address": [],
        "binding": [{
            "type": "ipv6",
            "address": "::",
            "port": 9735
        }, {
            "type": "ipv4",
            "address": "0.0.0.0",
            "port": 9735
        }],
        "version":
        "v0.9.3",
        "blockheight":
        0,
        "network":
        "testnet",
        "msatoshi_fees_collected":
        0,
        "fees_collected_msat":
        "0msat",
        "lightning-dir":
        "/data/lightning/testnet",
        "warning_bitcoind_sync":
        "Bitcoind is not up-to-date with network."
    }
    mock_get_info.return_value.json = lambda: SAMPLE_INFO

    get_info_rv = client.get('/info')
    get_json_resp = get_info_rv.get_json()
    assert get_info_rv.status_code == HTTPStatus.OK
    assert get_json_resp == SAMPLE_INFO


@patch('info.requests.get')
def test_get_info_failure(mock_get_info, client):
    mock_get_info.return_value = Mock()
    mock_get_info.return_value.status_code = HTTPStatus.UNAUTHORIZED
    get_info_rv = client.get('/info')
    assert get_info_rv.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert_error(get_info_rv.get_json(), 'LIGHTNING_CHARGE_INFO_FAILED')


@patch('info.requests.get')
def test_get_info_exception(mock_get_info, client):
    mock_get_info.side_effect = requests.exceptions.RequestException
    get_info_rv = client.get('/info')
    assert get_info_rv.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert_error(get_info_rv.get_json(), 'LIGHTNING_CHARGE_INFO_FAILED')
