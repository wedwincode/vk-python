from typing import Callable
from unittest.mock import mock_open

import pytest

from task8.function import get_valid_http_urls_from_file


@pytest.fixture(
    params=[
        (
            "https://example.com\n"
            "http://test.com\n",
            ["https://example.com", "http://test.com"],
        ),
        (
            "ftp://example.com\n"
            "not-url\n"
            "https://valid.com\n",
            ["https://valid.com"],
        ),
        (
            "\n"
            "   \n"
            "http://site.ru/path?q=1\n",
            ["http://site.ru/path?q=1"],
        ),
        (
            "http://\n"
            "https://\n"
            "example.com\n",
            [],
        ),
    ]
)
def file_content_case(request):
    """Возвращает tuple (content, expected_valid_list)."""
    return request.param


def mock_open_with_content(content: str) -> Callable:
    return mock_open(read_data=content)


def mock_open_raising_error(error: Exception) -> Callable:
    mocked_open = mock_open()
    mocked_open.side_effect = error
    return mocked_open


# custom implementation without unittest
def mock_open_with_content_no_unittest(content: str) -> Callable:
    class MockFile:
        def __init__(self, data: str):
            self._lines = data.splitlines(keepends=True)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def __iter__(self):
            return iter(self._lines)

    def _open(*args, **kwargs):
        return MockFile(content)

    return _open


# custom implementation without unittest
def mock_open_raising_error_no_unittest(error: Exception) -> Callable:
    def _open(*args, **kwargs):
        raise error
    return _open


def test_get_valid_http_urls_from_file(file_content_case, monkeypatch):
    content, expected = file_content_case

    monkeypatch.setattr("builtins.open", mock_open_with_content(content))

    actual = get_valid_http_urls_from_file("dummy_path")

    assert actual == expected


@pytest.mark.parametrize("error", [FileNotFoundError(), OSError("boom")])
def test_errors(monkeypatch, error):
    monkeypatch.setattr("builtins.open", mock_open_raising_error(error))

    if isinstance(error, FileNotFoundError):
        with pytest.raises(FileNotFoundError):
            get_valid_http_urls_from_file("dummy")
    else:
        with pytest.raises(IOError):
            get_valid_http_urls_from_file("dummy")