"""Single hard, partly-underspecified task: a Virtual Stack Machine interpreter.

The original spec (the user's prompt) leaves several things open: where the
stack lives, the byte-order of the GF vector, matrix row/col-major, and the
payload itself. So the test grades only the objectively-verifiable behavior,
using an interface pinned in the prompt (`run_vm`) plus checks that are
independent of the model's ordering conventions:

  * PUSH/POP with 64-bit values
  * STORE/LOAD with ring-buffer wrap across 0xFFFF -> 0x0000
  * JMP_IF_EQ taken and not-taken
  * immediate self-modifying fetch (a STORE overwrites a later instruction's
    operand bytes before IP reaches them)
  * GF(2^8) matmul (poly 0x11B) via identity and diagonal-x2 matrices, whose
    results don't depend on the model's byte/matrix ordering choice
"""

_PROMPT = r"""Write a fully self-contained Python 3 script that implements a deterministic Virtual Stack Machine (VSM) interpreter adhering strictly to the following specification:

1. Memory: Exactly 65,536 bytes (64KB) represented as a ring buffer (address arithmetic is modulo 65536). Program code and data share this single memory space starting at address 0x0000.
2. Registers: R0 through R7 (64-bit unsigned integers, wrapping at 2^64).
3. Fetch-Execute Cycle:
   - Fetching MUST happen byte-by-byte from memory[IP].
   - Self-modifying code must take effect IMMEDIATELY. If byte N is written to memory while IP < N, the fetch loop MUST read the new value when IP reaches N.
   - If an instruction modifies its own trailing operand bytes during execution, the current instruction uses the original fetched operands, but future fetches reflect the modified memory.
4. Opcodes (Hex):
   - 0x01: PUSH_IMM <8-byte uint64_le> -> pushes 64-bit int onto stack.
   - 0x02: POP <reg_idx: 1 byte> -> pops stack top into R[reg_idx].
   - 0x03: STORE_MEM <reg_src: 1 byte> <addr_reg: 1 byte> -> stores 8 bytes from R[reg_src] into memory at address held in R[addr_reg] (little-endian, ring-buffered).
   - 0x04: LOAD_MEM <reg_dst: 1 byte> <addr_reg: 1 byte> -> loads 8 bytes from memory at address held in R[addr_reg] into R[reg_dst].
   - 0x05: JMP_IF_EQ <reg1: 1 byte> <reg2: 1 byte> <target_addr: 2 bytes uint16_le> -> sets IP to target_addr if R[reg1] == R[reg2].
   - 0x06: GF_MATMUL <reg_src: 1 byte> <reg_dst: 1 byte> <matrix_addr_reg: 1 byte> -> Takes 8 bytes from R[reg_src] as an 8-element vector over GF(2^8) (poly 0x11B). Multiplies it by an 8x8 matrix of GF(2^8) elements stored at memory address R[matrix_addr_reg]. Writes the 8-byte result to R[reg_dst].
   - 0xFF: HALT.

5. Provide a verification function `run_test_payload()` that loads a 32-byte self-modifying loop starting at 0x0000 which uses GF_MATMUL to compute its own JMP_IF_EQ target address, modifies its own jump instruction in-place, and executes until R0 == 0xDEADBEEF.

Return ONLY working code with no placeholders or pseudo-code.

AUTOMATED VERIFICATION INTERFACE (in addition to everything above):
- Also define `run_vm(memory, max_steps=1000000)` that: copies `memory` (a bytes or
  bytearray) into a fresh 65536-byte image, zero-padded or truncated to exactly
  65536 bytes; runs the fetch-execute cycle starting at IP=0 until a HALT opcode
  executes (or max_steps instructions have run); and returns the final registers
  R0..R7 as a list of 8 Python ints.
- Registers start at 0; the stack starts empty (a Python list is fine).
- `run_test_payload()` may build on `run_vm`.
- Return the entire program as a single Python code block.
"""

_TEST = r"""
import struct

def u64(v):
    return struct.pack('<Q', v & ((1 << 64) - 1))

def gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF

# --- 1. PUSH_IMM / POP, 64-bit value ---
prog = bytes([0x01]) + u64(0xDEADBEEF) + bytes([0x02, 0x00, 0xFF])
r = run_vm(prog)
assert r[0] == 0xDEADBEEF, ("push/pop", r[0])

# --- 2. STORE_MEM / LOAD_MEM, no wrap ---
def build_sl(addr, val):
    return (bytes([0x01]) + u64(addr) + bytes([0x02, 0x01])
            + bytes([0x01]) + u64(val) + bytes([0x02, 0x02])
            + bytes([0x03, 0x02, 0x01])
            + bytes([0x04, 0x03, 0x01])
            + bytes([0xFF]))
r = run_vm(build_sl(100, 0x1122334455667788))
assert r[3] == 0x1122334455667788, ("store/load", r[3])

# --- 2b. ring-buffer wrap across 0xFFFF -> 0x0000 ---
r = run_vm(build_sl(65533, 0xA1A2A3A4A5A6A7A8))
assert r[3] == 0xA1A2A3A4A5A6A7A8, ("wrap store/load", r[3])

# --- 3. JMP_IF_EQ taken and not-taken (target lands at index 49) ---
def build_jmp(v):
    return (bytes([0x01]) + u64(0x777) + bytes([0x02, 0x02])      # R2 = 0x777
            + bytes([0x01]) + u64(5) + bytes([0x02, 0x00])        # R0 = 5
            + bytes([0x01]) + u64(v) + bytes([0x02, 0x01])        # R1 = v
            + bytes([0x05, 0x00, 0x01]) + struct.pack('<H', 49)   # JMP_IF_EQ R0,R1,49
            + bytes([0x01]) + u64(0xBAD) + bytes([0x02, 0x02])    # R2 = 0xBAD (skipped if taken)
            + bytes([0xFF]))                                      # index 49: HALT
r = run_vm(build_jmp(5))
assert r[2] == 0x777, ("jmp taken", r[2])
r = run_vm(build_jmp(6))
assert r[2] == 0xBAD, ("jmp not-taken", r[2])

# --- 4. immediate self-modifying fetch ---
# STORE (executing at IP=22) overwrites the immediate at [26..33] of the later
# PUSH_IMM before IP reaches it, so R3 must read the NEW value.
prog = (bytes([0x01]) + u64(26) + bytes([0x02, 0x01])            # R1 = 26
        + bytes([0x01]) + u64(0xCAFEBABE) + bytes([0x02, 0x02])  # R2 = 0xCAFEBABE
        + bytes([0x03, 0x02, 0x01])                              # STORE R2 -> [26]
        + bytes([0x01]) + u64(0x11111111) + bytes([0x02, 0x03])  # PUSH orig; POP R3
        + bytes([0xFF]))
r = run_vm(prog)
assert r[3] == 0xCAFEBABE, ("self-modifying fetch", hex(r[3]))

# --- 5a. GF_MATMUL with identity matrix -> result == input (convention-free) ---
def build_gf_image(matrix_bytes, vec):
    img = bytearray(300)
    prog = (bytes([0x01]) + u64(200) + bytes([0x02, 0x01])       # R1 = 200 (matrix addr)
            + bytes([0x01]) + u64(vec) + bytes([0x02, 0x02])     # R2 = vec
            + bytes([0x06, 0x02, 0x03, 0x01])                    # GF_MATMUL R2->R3 @ [R1]
            + bytes([0xFF]))
    img[0:len(prog)] = prog
    img[200:200 + 64] = matrix_bytes
    return bytes(img)

identity = bytearray(64)
for i in range(8):
    identity[i * 8 + i] = 0x01
V = 0x0102030405060708
r = run_vm(build_gf_image(bytes(identity), V))
assert r[3] == V, ("gf identity", hex(r[3]))

# --- 5b. GF_MATMUL with diagonal x2 -> each byte = gmul(2, byte) (exercises 0x11B) ---
diag2 = bytearray(64)
for i in range(8):
    diag2[i * 8 + i] = 0x02
V2 = 0x8001FF1053CA0288
vb = V2.to_bytes(8, 'little')
expected = int.from_bytes(bytes(gmul(2, x) for x in vb), 'little')
r = run_vm(build_gf_image(bytes(diag2), V2))
assert r[3] == expected, ("gf mul-by-2", hex(r[3]), hex(expected))
"""

TASKS = [
    {
        "id": "v1_vsm_interpreter",
        "level": "systems",
        "prompt": _PROMPT,
        "test_code": _TEST,
    },
]
