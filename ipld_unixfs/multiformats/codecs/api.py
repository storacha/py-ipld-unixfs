# TODO: PR to multiformats?
from abc import abstractmethod
from typing import Generic, Protocol, TypeVar
import multiformats


Code = TypeVar("Code", bound=int)
"""IPLD codec code."""

Data = TypeVar("Data", contravariant=True)


class BlockEncoder(Protocol[Code, Data]):
    """
    IPLD encoder part of the codec.
    """

    name: str
    code: Code

    def encode(self, data: Data) -> bytes: ...
