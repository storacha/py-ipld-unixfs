# TODO: PR to multiformats?
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")

CodeT = TypeVar("CodeT", bound=int)
"""IPLD codec code."""


class ByteView(bytes, Generic[T]):
    """
    A byte-encoded representation of some data of type `T`

    A `ByteView` is essentially a `bytes` that's been "tagged" with
    arbitrary data of type `T` indicating the type of encoded data.

    For example a `ByteView[dict]` is a series of `bytes` containing a
    binary representation of `dict`.
    """


class BlockEncoder(Protocol[CodeT, T]):
    """
    IPLD encoder part of the codec.
    """

    name: str
    code: CodeT

    def encode(self, data: T) -> ByteView[T]: ...
