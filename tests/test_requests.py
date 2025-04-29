from unittest.mock import MagicMock, patch

import pytest
from aiohttp.test_utils import make_mocked_request
from sqlalchemy import Column, Integer, String

from lightapi.database import Base
from lightapi.handlers import (
    CreateHandler,
    DeleteHandler,
    HeadHandler,
    OptionsHandler,
    PatchHandler,
    ReadHandler,
    RetrieveAllHandler,
    UpdateHandler,
)


class MockModel(Base):
    __tablename__ = 'mockmodel'
    id = Column(Integer, primary_key=True, autoincrement=True)
    field1 = Column(String)
    field2 = Column(String)

    def serialize(self):
        return {
            "id": self.id,
            "field1": self.field1,
            "field2": self.field2,
        }


@pytest.fixture
def mock_session():
    with patch('lightapi.handlers.SessionLocal') as session_mock:
        session = session_mock.return_value
        yield session


@pytest.fixture
def test_data():
    return {"field1": "value1", "field2": "value2"}


@pytest.mark.asyncio
async def test_create_handler(mock_session, test_data):
    handler = CreateHandler(model=MockModel)
    request = make_mocked_request(
        'POST',
        '/',
        headers={'Content-Type': 'application/json'},
        payload=str(test_data),
    )

    mock_session.query(MockModel).filter.return_value.first.return_value = None
    response = await handler.handle(mock_session, request)

    assert response.status == 201


@pytest.mark.asyncio
async def test_read_handler_existing_item(mock_session):
    handler = ReadHandler(model=MockModel)
    mock_item = MagicMock(spec=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = mock_item

    request = make_mocked_request('GET', '/1', match_info={'id': '1'})
    response = await handler.handle(mock_session, request)

    assert response.status == 200


@pytest.mark.asyncio
async def test_read_handler_missing_item(mock_session):
    handler = ReadHandler(model=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = None

    request = make_mocked_request('GET', '/1', match_info={'id': '1'})
    response = await handler.handle(mock_session, request)

    assert response.status == 404


@pytest.mark.asyncio
async def test_update_handler_existing_item(mock_session, test_data):
    handler = UpdateHandler(model=MockModel)
    mock_item = MagicMock(spec=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = mock_item

    request = make_mocked_request(
        'PUT',
        '/1',
        headers={'Content-Type': 'application/json'},
        payload=str(test_data),
        match_info={'id': '1'},
    )
    response = await handler.handle(mock_session, request)

    assert response.status == 200


@pytest.mark.asyncio
async def test_update_handler_missing_item(mock_session, test_data):
    handler = UpdateHandler(model=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = None

    request = make_mocked_request(
        'PUT',
        '/1',
        headers={'Content-Type': 'application/json'},
        payload=str(test_data),
        match_info={'id': '1'},
    )
    response = await handler.handle(mock_session, request)

    assert response.status == 404


@pytest.mark.asyncio
async def test_delete_handler_existing_item(mock_session):
    handler = DeleteHandler(model=MockModel)
    mock_item = MagicMock(spec=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = mock_item

    request = make_mocked_request('DELETE', '/1', match_info={'id': '1'})
    response = await handler.handle(mock_session, request)

    assert response.status == 204


@pytest.mark.asyncio
async def test_delete_handler_missing_item(mock_session):
    handler = DeleteHandler(model=MockModel)
    mock_session.query(MockModel).filter.return_value.first.return_value = None

    request = make_mocked_request('DELETE', '/1', match_info={'id': '1'})
    response = await handler.handle(mock_session, request)

    assert response.status == 404


@pytest.mark.asyncio
async def test_retrieve_all_handler(mock_session):
    handler = RetrieveAllHandler(model=MockModel)
    mock_items = [MagicMock(spec=MockModel), MagicMock(spec=MockModel)]
    mock_session.query(MockModel).all.return_value = mock_items

    request = make_mocked_request('GET', '/')
    response = await handler.handle(mock_session, request)

    assert response.status == 200


@pytest.mark.asyncio
async def test_options_handler(mock_session):
    handler = OptionsHandler(model=MockModel)
    request = make_mocked_request('OPTIONS', '/')

    response = await handler.handle(mock_session, request)

    assert response.status == 200


@pytest.mark.asyncio
async def test_head_handler(mock_session):
    handler = HeadHandler(model=MockModel)
    request = make_mocked_request('HEAD', '/')

    response = await handler.handle(mock_session, request)

    assert response.status == 200
