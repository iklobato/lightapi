from unittest.mock import MagicMock

import pytest

from lightapi.filters import BaseFilter, ParameterFilter


class TestFilters:
    def test_base_filter_queryset(self):
        filter_obj = BaseFilter()
        mock_queryset = MagicMock()
        mock_request = MagicMock()
        result = filter_obj.filter_queryset(mock_queryset, mock_request)
        assert result == mock_queryset

    def test_parameter_filter_queryset_no_params(self):
        filter_obj = ParameterFilter()
        mock_queryset = MagicMock()
        mock_request = MagicMock()
        mock_request.query_params = {}
        result = filter_obj.filter_queryset(mock_queryset, mock_request)
        assert result == mock_queryset

    def test_parameter_filter_queryset_with_params(self):
        filter_obj = ParameterFilter()
        mock_queryset = MagicMock()
        mock_entity = MagicMock()
        mock_entity.name = "test_name"
        mock_entity.id = 1
        mock_queryset.column_descriptions = [{"entity": mock_entity}]
        mock_filtered = MagicMock()
        mock_queryset.filter.return_value = mock_filtered
        mock_request = MagicMock()
        mock_request.query_params = {"name": "test_name", "id": "1"}
        result = filter_obj.filter_queryset(mock_queryset, mock_request)
        assert mock_queryset.filter.call_count == 2
        assert result == mock_filtered
