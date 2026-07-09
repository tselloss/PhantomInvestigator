from unittest.mock import MagicMock, patch

import pytest

import vision


def test_describe_screenshot_returns_extracted_text():
    fake_provider = MagicMock()
    fake_provider.vision.return_value = "Error 500 on /checkout"
    with patch.object(vision.providers, "get_provider", return_value=fake_provider):
        result = vision.describe_screenshot(b"fake-image-bytes", "image/png", 1)
    assert result == "Error 500 on /checkout"


def test_describe_screenshot_passes_image_bytes_and_content_type():
    fake_provider = MagicMock()
    fake_provider.vision.return_value = "ok"
    with patch.object(vision.providers, "get_provider", return_value=fake_provider):
        vision.describe_screenshot(b"fake-image-bytes", "image/png", 1)

    args, _ = fake_provider.vision.call_args
    assert args[0] == b"fake-image-bytes"
    assert args[1] == "image/png"
    assert args[2] == vision.EXTRACTION_PROMPT


def test_describe_screenshot_propagates_errors():
    fake_provider = MagicMock()
    fake_provider.vision.side_effect = TimeoutError("boom")
    with patch.object(vision.providers, "get_provider", return_value=fake_provider):
        with pytest.raises(TimeoutError):
            vision.describe_screenshot(b"fake-image-bytes", "image/png", 1)
