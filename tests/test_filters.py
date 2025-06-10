from unittest.mock import MagicMock

import pytest

from lightapi.filters import BaseFilter, ParameterFilter


class TestBaseFilter:
    def test_filter_queryset(self):
        filter_obj = BaseFilter()
        mock_queryset = MagicMock()
        mock_request = MagicMock()

        result = filter_obj.filter_queryset(mock_queryset, mock_request)

        assert result == mock_queryset


class TestParameterFilter:
    def test_filter_queryset_no_params(self):
        filter_obj = ParameterFilter()
        mock_queryset = MagicMock()
        mock_request = MagicMock()
        mock_request.query_params = {}

        result = filter_obj.filter_queryset(mock_queryset, mock_request)

        assert result == mock_queryset

    def test_filter_queryset_with_params(self):
        filter_obj = ParameterFilter()

        # Create mock queryset and entity
        mock_queryset = MagicMock()
        mock_entity = MagicMock()
        mock_entity.name = "test_name"
        mock_entity.id = 1

        # Set up column_descriptions to return our entity
        mock_queryset.column_descriptions = [{"entity": mock_entity}]

        # Create filtered queryset mock
        mock_filtered = MagicMock()
        mock_queryset.filter.return_value = mock_filtered

        # Create mock request with query params
        mock_request = MagicMock()
        mock_request.query_params = {"name": "test_name", "id": "1"}

        # Call filter_queryset
        result = filter_obj.filter_queryset(mock_queryset, mock_request)

        # Check that filter was called with the correct arguments
        assert mock_queryset.filter.call_count == 2

        # Check that the filtered queryset was returned
        assert result == mock_filtered
