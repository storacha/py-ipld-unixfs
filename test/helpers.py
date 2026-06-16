import asyncio
import hashlib
from ipld_unixfs import unixfs
from ipld_unixfs.file import interfaces as API


class MemoryBlockWriter(API.BlockWriter):
    def __init__(self) -> None:
        self.blocks: list[unixfs.Block] = []
        self._closed = False
        self._ready_future = asyncio.get_running_loop().create_future()
        self._ready_future.set_result(None)

    @property
    def desired_size(self) -> float | None:
        return 1.0

    @property
    def ready(self) -> asyncio.Future:
        return self._ready_future

    def release_lock(self) -> None:
        pass

    async def write(self, data: unixfs.Block) -> None:
        self.blocks.append(data)

    async def close(self) -> None:
        self._closed = True

    async def abort(self, reason: Exception) -> None:
        self._closed = True

from multiformats import multihash

async def hashrecur(seed: bytes = b"hello world", byte_length: float = float("inf")):
    value = seed
    byte_offset = 0
    sha256 = multihash.get("sha2-256")
    while True:
        value = sha256.digest(value).digest
        size = byte_length - byte_offset
        if size < len(value):
            yield value[:int(size)]
            break
        else:
            byte_offset += len(value)
            yield value

