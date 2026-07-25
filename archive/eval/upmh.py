"""Reference implementation of the UPMH-64 spec -- the deterministic oracle.

Run directly to print the canonical answer:  py upmh.py
"""

MASK = 0xFFFFFFFFFFFFFFFF
GOLDEN = 0x9E3779B97F4A7C15
SEED = b"Fable_Sol_Canonical_Test_2026"


def upmh64() -> int:
    S = list(range(256))
    ACC = 0x0123456789ABCDEF
    L = len(SEED)  # 29

    # Key schedule
    j = 0
    for i in range(256):
        j = (j + S[i] + SEED[i % L]) & 0xFF
        S[i], S[j] = S[j], S[i]

    # 65,536 rounds
    for r in range(65536):
        a = (r ^ (ACC & 0xFF)) & 0xFF
        b = (S[a] + (ACC >> 56)) & 0xFF
        S[a], S[b] = S[b], S[a]
        val = S[(S[a] + S[b]) & 0xFF] ^ (r & 0xFF)
        ACC = ((ACC << 13) | (ACC >> 51)) & MASK
        ACC = (ACC ^ (val * GOLDEN)) & MASK
        if ACC & 1:
            ACC = (ACC ^ S[r & 0xFF]) & MASK

    tail = 0
    for k in range(8):
        tail |= S[k] << (8 * k)
    return (ACC ^ tail) & MASK


def canonical() -> str:
    return "0x" + format(upmh64(), "016X")


if __name__ == "__main__":
    print(canonical())
