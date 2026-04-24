from typing import Protocol, TypeAlias, TypeVar
from ipld_unixfs.types import BytesLike

Code = TypeVar("Code", bound=int)

class MultihashDigest(Protocol[Code]):
    """
    Represents a multihash digest which carries information about the
    hashing algorithm and actual hash digest.
    """
    code: Code
    """Code of the multihash."""
    digest: BytesLike
    """Raw binary digest without multihash info"""
    size: int
    """Bytes length of the `self.digest`"""
    mh_bytes: BytesLike
    """Binary representation of the multihash digest"""


class MultihashHasher(Protocol[Code]):
    """
    Represents a hashing algorithm implementation that produces a
    multihash digest.
    """
    name: str
    code: Code

    def digest(self, input: BytesLike) -> MultihashDigest: ...
