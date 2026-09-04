"""
Pure-Python Keccak-256 (the pre-NIST padding variant Ethereum uses).

Exists so `polymarket.py` can DERIVE Gnosis CTF event topic0 hashes from their
canonical signature strings at import time instead of carrying hard-coded 32-byte
constants that nobody can check by eye. No web3/eth-hash/pysha3 dependency, and
no network: the agent stays deterministic and local.

Note this is Keccak-256, NOT hashlib's sha3_256 - they differ only in the padding
byte (0x01 vs 0x06), which is exactly why substituting one for the other silently
produces topics that match nothing on chain.
"""
from typing import List

_MASK64 = (1 << 64) - 1
_RATE_BYTES = 136  # 1088-bit rate for Keccak-256

_ROUND_CONSTANTS = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)

# Rho rotation offsets, indexed [x][y].
_ROTATION_OFFSETS = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)


def _rotl64(value: int, shift: int) -> int:
    if shift == 0:
        return value
    return ((value << shift) | (value >> (64 - shift))) & _MASK64


def _keccak_f1600(state: List[List[int]]) -> None:
    """In-place Keccak-f[1600] permutation over a 5x5 lane matrix."""
    for rnd in range(24):
        # Theta
        col_parity = [
            state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4]
            for x in range(5)
        ]
        theta_d = [
            col_parity[(x - 1) % 5] ^ _rotl64(col_parity[(x + 1) % 5], 1)
            for x in range(5)
        ]
        for x in range(5):
            for y in range(5):
                state[x][y] ^= theta_d[x]

        # Rho + Pi
        scratch = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                scratch[y][(2 * x + 3 * y) % 5] = _rotl64(state[x][y], _ROTATION_OFFSETS[x][y])

        # Chi
        for x in range(5):
            for y in range(5):
                state[x][y] = scratch[x][y] ^ ((~scratch[(x + 1) % 5][y]) & _MASK64 & scratch[(x + 2) % 5][y])

        # Iota
        state[0][0] ^= _ROUND_CONSTANTS[rnd]


def _sponge(data: bytes, pad_byte: int) -> bytes:
    """
    The Keccak sponge at rate 1088 / capacity 512, squeezing 32 bytes.

    `pad_byte` is the ONLY thing separating the two functions built on this:
    0x01 is original Keccak (what Ethereum uses), 0x06 is NIST SHA-3. Exposing it
    is what lets the tests pin this implementation against hashlib's SHA3-256
    across multi-block inputs. The permutation, the absorb loop and the block
    boundaries are shared, so agreeing with a known-good implementation at 0x06
    is real evidence that the 0x01 path is right too - far better than asserting
    that a digest is 32 bytes long, which every wrong implementation also does.
    """
    # Pad10*1 with the caller's domain byte.
    padded = bytearray(data)
    pad_len = _RATE_BYTES - (len(padded) % _RATE_BYTES)
    if pad_len == 1:  # domain byte and the 0x80 terminator collapse onto one byte
        padded.append(pad_byte | 0x80)
    else:
        padded.append(pad_byte)
        padded.extend(b"\x00" * (pad_len - 2))
        padded.append(0x80)

    state = [[0] * 5 for _ in range(5)]
    for block_start in range(0, len(padded), _RATE_BYTES):
        block = padded[block_start:block_start + _RATE_BYTES]
        for lane in range(_RATE_BYTES // 8):
            x, y = lane % 5, lane // 5
            state[x][y] ^= int.from_bytes(block[lane * 8:lane * 8 + 8], "little")
        _keccak_f1600(state)

    out = bytearray()
    for lane in range(4):  # 32 bytes of squeeze is well inside one rate block
        x, y = lane % 5, lane // 5
        out.extend(state[x][y].to_bytes(8, "little"))
    return bytes(out)


def keccak256(data: bytes) -> bytes:
    """Returns the 32-byte Keccak-256 digest of `data` (the variant Ethereum uses)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"keccak256 expects bytes, got {type(data).__name__}")
    return _sponge(bytes(data), 0x01)


def sha3_256(data: bytes) -> bytes:
    """
    NIST SHA3-256 off the same sponge. Nothing in production calls this - it
    exists so the tests can pin the permutation against `hashlib.sha3_256`.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return _sponge(bytes(data), 0x06)


def event_topic(signature: str) -> str:
    """'PositionSplit(address,...)' -> '0x<64 hex chars>' topic0 for eth_getLogs."""
    return "0x" + keccak256(signature.encode("utf-8")).hex()


# Known-answer self check. If this ever fails, every derived topic is garbage and
# every on-chain sync would silently return zero logs, so fail loudly at import.
_KAT_EMPTY = "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
_KAT_TRANSFER = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
if keccak256(b"").hex() != _KAT_EMPTY or event_topic("Transfer(address,address,uint256)")[2:] != _KAT_TRANSFER:
    raise RuntimeError("keccak256 self-test failed - CTF event topics would be wrong")
