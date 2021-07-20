import pytest
from http import HTTPStatus

import server


@pytest.fixture
def client():
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


def test_get_info_successfuly(client):
    get_queues_rv = client.get('/queue.html')
    assert get_queues_rv.status_code == HTTPStatus.OK
    assert get_queues_rv.content_type == 'text/html'
