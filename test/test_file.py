import pytest

CHUNK_SIZE = 262144


@pytest.mark.timeout(30000)
async def test_basic_file():
    content = "this file does not have much content\n".encode("utf-8")
