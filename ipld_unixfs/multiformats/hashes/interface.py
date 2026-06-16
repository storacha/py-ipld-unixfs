from typing import Generic, TypeAlias, TypeVar
from multiformats import multihash, multicodec

# Removed int, str to avoid layout conflict with multicodec.Multicodec
class Code(multicodec.Multicodec):
    """Code that indicates the hashing algorithm of the Multihash"""
    pass

CodeT = TypeVar(name="CodeT", bound=Code)

MultihashDigest: TypeAlias = bytes

class Multihash(multihash.Multihash, Generic[CodeT]):
    pass
