import pytest
from ipld_unixfs import file, unixfs
from .helpers import MemoryBlockWriter

CHUNK_SIZE = 262144

@pytest.mark.timeout(30000)
async def test_basic_file():
    content = "this file does not have much content\n".encode("utf-8")
    writer = MemoryBlockWriter()

    settings = file.defaults()

    fw = file.create(file.API.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))

    await fw.write(content)
    link = await fw.close(file.API.CloseOptions(release_lock=False, close_writer=True))

    assert link.content_byte_length == 37
    assert link.dag_byte_length == 45
    assert str(link.cid) == "bafybeidequ5soq6smzafv4lb76i5dkvl5fzgvrxz4bmlc2k4dkikklv2j4"

    assert len(writer.blocks) == 1
    block = writer.blocks[0]
    assert str(block.cid) == "bafybeidequ5soq6smzafv4lb76i5dkvl5fzgvrxz4bmlc2k4dkikklv2j4"


@pytest.mark.timeout(30000)
async def test_splits_into_3_chunks():
    writer = MemoryBlockWriter()
    fw = file.create(file.API.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=file.defaults()
    ))

    await fw.write(bytes([1]) * CHUNK_SIZE)
    await fw.write(bytes([2]) * CHUNK_SIZE)
    await fw.write(bytes([3]) * CHUNK_SIZE)
    link = await fw.close(file.API.CloseOptions(release_lock=False, close_writer=True))

    assert link.content_byte_length == 786432
    assert link.dag_byte_length == 786632
    assert str(link.cid) == "bafybeiegda62p2cdi5sono3h3hqjnxwc56z4nocynrj44rz7rtc2p246cy"

    assert len(writer.blocks) == 4 # 3 chunks + 1 root
    cids = [str(b.cid) for b in writer.blocks]
    assert "bafybeihhsdoupgd3fnl3e3367ymsanmikafpllldsdt37jzyoh6nuatowe" in cids
    assert "bafybeief3dmadxfymhhhrflqytqmlhlz47w6glaxvyzmm6s6tpfb6izzee" in cids
    assert "bafybeihznihf5g5ibdyoawn7uu3inlyqrxjv63lt6lop6h3w6rzwrp67a4" in cids
    assert str(writer.blocks[3].cid) == "bafybeiegda62p2cdi5sono3h3hqjnxwc56z4nocynrj44rz7rtc2p246cy"


@pytest.mark.timeout(30000)
async def test_chunker_size_65535():
    chunk_size = 65535
    writer = MemoryBlockWriter()

    from ipld_unixfs.file.chunker import fixed as FixedSize

    settings = file.defaults()
    settings.chunker = FixedSize.with_max_chunk_size(chunk_size)

    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))

    size = round(chunk_size * 2.2)
    frame = round(size / 10)
    offset = 0
    n = 0
    while offset < size:
        data_size = min(frame, size - offset)
        n += 1
        await fw.write(bytes([n % 256]) * data_size)
        offset += frame

    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))

    assert link.content_byte_length == 144177
    assert link.dag_byte_length == 144372
    assert str(link.cid) == "bafybeiduffmtppi4cwa6olo3ggmoehvtdtcd47y6ddoodhyvcv7y3zvgnq"


@pytest.mark.timeout(30000)
async def test_write_empty():
    writer = MemoryBlockWriter()
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=file.defaults()
    ))

    await fw.write(b"")
    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))

    assert link.content_byte_length == 0
    assert link.dag_byte_length == 6
    assert str(link.cid) == "bafybeif7ztnhq65lumvvtr4ekcwd2ifwgm3awq4zfr3srh462rwyinlb4y"


@pytest.mark.timeout(30000)
async def test_close_writer():
    writer = MemoryBlockWriter()
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=file.defaults()
    ))

    content = "this file does not have much content\n".encode("utf-8")
    await fw.write(content)
    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))

    assert writer._closed is True
    assert str(link.cid) == "bafybeidequ5soq6smzafv4lb76i5dkvl5fzgvrxz4bmlc2k4dkikklv2j4"


@pytest.mark.timeout(30000)
async def test_release_lock():
    class LockWriter(MemoryBlockWriter):
        def __init__(self):
            super().__init__()
            self.locked = True
        def release_lock(self):
            self.locked = False
            
    writer = LockWriter()
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=file.defaults()
    ))
    
    content = "this file does not have much content\n".encode("utf-8")
    await fw.write(content)
    link = await fw.close(file.CloseOptions(release_lock=True, close_writer=False))
    
    assert writer.locked is False
    assert writer._closed is False
    assert str(link.cid) == "bafybeidequ5soq6smzafv4lb76i5dkvl5fzgvrxz4bmlc2k4dkikklv2j4"


@pytest.mark.timeout(30000)
async def test_can_create_writer_from_other_writer():
    writer = MemoryBlockWriter()
    settings = file.defaults()
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))
    
    fw2 = file.create(file.Options(
        writer=fw.writer,
        metadata=fw.state.metadata,
        settings=fw.settings
    ))
    
    assert fw2.writer is writer
    assert fw2.settings is settings


@pytest.mark.timeout(30000)
async def test_trickle_layout():
    from ipld_unixfs.file.layout import trickle as Trickle
    from .helpers import hashrecur

    content = hashrecur(byte_length=CHUNK_SIZE * 2)
    writer = MemoryBlockWriter()
    settings = file.configure(
        chunker=file.with_max_chunk_size(1300),
        file_layout=Trickle.TrickleLayout(),
        file_chunk_encoder=file.UnixFSRawLeaf()
    )

    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))

    async for slice in content:
        await fw.write(slice)

    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))

    assert link.content_byte_length == 524288
    assert link.dag_byte_length == 548251
    assert str(link.cid) == "bafybeidia54tfr7ycw2ls2mxyjpcto42mriytx2ymlwgwsjqzner5wqc5u"


@pytest.mark.timeout(30000)
async def test_trickle_layout_with_overflow():
    from ipld_unixfs.file.layout import trickle as Trickle
    from .helpers import hashrecur
    
    content = hashrecur(byte_length=CHUNK_SIZE * 2)
    writer = MemoryBlockWriter()
    settings = file.configure(
        chunker=file.with_max_chunk_size(100000),
        file_layout=Trickle.TrickleLayout(Trickle.Options(max_direct_leaves=5)),
        file_chunk_encoder=file.UnixFSRawLeaf()
    )
    
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))
    
    async for slice in content:
        await fw.write(slice)
        
    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))
    
    assert link.content_byte_length == 524288
    assert link.dag_byte_length == 524738
    assert str(link.cid) == "bafybeigu6bkvpxtamauopeu2ejzkxy4wgqa576wmfc6ubusjwhgold4aum"


@pytest.mark.timeout(30000)
async def test_trickle_with_several_levels_deep():
    from ipld_unixfs.file.layout import trickle as Trickle
    from .helpers import hashrecur
    
    chunk_size = 128
    max_leaves = 4
    leaf_count = 42
    
    content = hashrecur(byte_length=chunk_size * leaf_count)
    writer = MemoryBlockWriter()
    settings = file.configure(
        chunker=file.with_max_chunk_size(chunk_size),
        file_layout=Trickle.TrickleLayout(Trickle.Options(max_direct_leaves=max_leaves)),
        file_chunk_encoder=file.UnixFSRawLeaf()
    )
    
    fw = file.create(file.Options(
        writer=writer,
        metadata=unixfs.Metadata(),
        settings=settings
    ))
    
    async for slice in content:
        await fw.write(slice)
        
    link = await fw.close(file.CloseOptions(release_lock=False, close_writer=True))
    
    assert link.content_byte_length == chunk_size * leaf_count
    assert link.dag_byte_length == 8411
    assert str(link.cid) == "bafybeieyaff3xepdv5r56bnhgxbxpjy6pzvxqpc6abjtkk4f46ylwop5ga"
