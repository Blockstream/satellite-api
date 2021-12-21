import pytest


@pytest.fixture
def mockredis(mocker):
    _mr = mocker.Mock(name="mockredis")
    mocker.patch("transmitter.redis", return_value=_mr)
    mocker.patch("transmitter.redis.from_url", return_value=_mr)
    return _mr
