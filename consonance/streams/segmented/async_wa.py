import asyncio
import struct
from typing import Optional

from .async_segmented import AsyncSegmentedStream


class AsyncWASegmentedStream(AsyncSegmentedStream):
    """Async WASegmentedStream backed by asyncio.StreamReader/StreamWriter."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    async def read_segment(self) -> bytes:
        header = await self._reader.readexactly(3)
        size = struct.unpack('>I', b"\x00" + header)[0]
        return await self._reader.readexactly(size)

    async def write_segment(self, data: bytes) -> None:
        if len(data) >= 16777216:
            raise ValueError(f"data too large to write; length={len(data)}")
        self._writer.write(struct.pack('>I', len(data))[1:])
        self._writer.write(data)
        await self._writer.drain()
