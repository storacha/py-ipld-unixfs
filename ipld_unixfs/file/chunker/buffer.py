from typing import Optional, Self


class BufferView:
    segments: list[memoryview]
    byte_length: int
    byte_offset: int

    def __init__(
        self,
        segments: list[memoryview] = [],
        byte_length: int = 0,
        byte_offset: int = 0,
    ) -> None:
        self.segments = segments
        self.byte_length = byte_length
        self.byte_offset = byte_offset

    def slice(self, start: int = 0, end: Optional[int] = None) -> Self:
        return self

    def copy_to(self, target: memoryview, offset: int) -> memoryview:
        return target
