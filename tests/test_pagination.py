from unittest.mock import MagicMock

import pytest

from lightapi.pagination import Paginator


class CustomPaginator(Paginator):
    limit = 20
    offset = 5
    sort = True

    def apply_sorting(self, queryset):
        return queryset.order_by("id")


class TestPaginator:
    def test_default_paginator(self):
        paginator = Paginator()
        assert paginator.limit == 10
        assert paginator.offset == 0
        assert paginator.sort is False

    def test_custom_paginator(self):
        paginator = CustomPaginator()
        assert paginator.limit == 20
        assert paginator.offset == 5
        assert paginator.sort is True

    def test_get_limit(self):
        paginator = Paginator()
        assert paginator.get_limit() == 10

        custom_paginator = CustomPaginator()
        assert custom_paginator.get_limit() == 20

    def test_get_offset(self):
        paginator = Paginator()
        assert paginator.get_offset() == 0

        custom_paginator = CustomPaginator()
        assert custom_paginator.get_offset() == 5

    def test_paginate(self):
        paginator = Paginator()

        # Create a mock queryset
        mock_queryset = MagicMock()
        mock_limited = MagicMock()
        mock_queryset.limit.return_value = mock_limited
        mock_offset = MagicMock()
        mock_limited.offset.return_value = mock_offset
        mock_results = [{"id": 1}, {"id": 2}]
        mock_offset.all.return_value = mock_results

        # Test pagination
        results = paginator.paginate(mock_queryset)

        # Verify correct methods were called
        mock_queryset.limit.assert_called_once_with(10)
        mock_limited.offset.assert_called_once_with(0)
        mock_offset.all.assert_called_once()

        # Verify results
        assert results == mock_results

    def test_paginate_with_sorting(self):
        paginator = CustomPaginator()

        # Create a mock queryset
        mock_queryset = MagicMock()
        mock_sorted = MagicMock()
        mock_queryset.order_by.return_value = mock_sorted
        mock_limited = MagicMock()
        mock_sorted.limit.return_value = mock_limited
        mock_offset = MagicMock()
        mock_limited.offset.return_value = mock_offset
        mock_results = [{"id": 1}, {"id": 2}]
        mock_offset.all.return_value = mock_results

        # Test pagination with sorting
        results = paginator.paginate(mock_queryset)

        # Verify correct methods were called
        mock_queryset.order_by.assert_called_once_with("id")
        mock_sorted.limit.assert_called_once_with(20)
        mock_limited.offset.assert_called_once_with(5)
        mock_offset.all.assert_called_once()

        # Verify results
        assert results == mock_results
