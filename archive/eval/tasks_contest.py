"""Three recent contest-style problems (less likely memorized than textbook ones).

Expected test values are hand-verified against the problem statements.
Run just these with:  uv run --with anthropic python run_eval.py tasks_contest
"""

TASKS = [
    {
        "id": "c1_final_state",
        "level": "contest",
        "prompt": (
            "Write a Python function `getFinalState(nums: list[int], k: int, "
            "multiplier: int) -> list[int]`. Perform k operations on nums. In each "
            "operation: find the minimum value x in nums (if it occurs multiple times, "
            "pick the first occurrence) and replace that element with x * multiplier. "
            "After all k operations, apply modulo 10**9 + 7 to every value. Return the "
            "final array."
        ),
        "test_code": """
MOD = 10**9 + 7
assert getFinalState([2,1,3,5,6], 5, 2) == [8,4,6,5,6]
assert getFinalState([1,2], 3, 4) == [16,8]
assert getFinalState([1], 2, 3) == [9]
assert getFinalState([1000000000], 1, 2) == [(2000000000) % MOD]  # 999999993
""",
    },
    {
        "id": "c2_alt_sum_product",
        "level": "contest",
        "prompt": (
            "Write a Python function `maxProduct(nums: list[int], k: int, limit: int) "
            "-> int`. Find a non-empty subsequence of nums whose alternating sum equals "
            "k and whose product of all its numbers is maximized without exceeding "
            "limit. Return that product, or -1 if no subsequence satisfies both. The "
            "alternating sum is the sum of elements at even indices (0-based, within "
            "the subsequence) minus the sum of elements at odd indices."
        ),
        "test_code": """
assert maxProduct([1,2,3], 2, 10) == 6
assert maxProduct([0,2,3], -5, 12) == -1
assert maxProduct([2,2,3,3], 0, 9) == 9
""",
    },
    {
        "id": "c3_max_subarray_swaps",
        "level": "contest",
        "prompt": (
            "Write a Python function `maxSubarraySum(nums: list[int], k: int) -> int`. "
            "You may perform at most k swap operations on the array; in one swap you "
            "choose any two indices i and j and swap nums[i] and nums[j]. After "
            "performing the swaps, return the maximum possible sum of any non-empty "
            "contiguous subarray of the resulting array. Choose the swaps to maximize "
            "that value."
        ),
        "test_code": """
assert maxSubarraySum([1,2,3,4,5], 0) == 15
assert maxSubarraySum([-1,-2,-3], 0) == -1
assert maxSubarraySum([10,-5,-5,-5,9], 1) == 19
assert maxSubarraySum([8,8,-100,-100,7,7], 2) == 30
""",
    },
    {
        "id": "c4_card_pairs",
        "level": "contest",
        "prompt": (
            "Write a Python function `maxScore(cards: list[str], x: str) -> int`. Each "
            "card is a string of two lowercase letters. Repeatedly remove a pair of "
            "compatible cards, earning 1 point per removed pair, until no compatible "
            "pair remains. Two cards are compatible if BOTH contain the letter x (in "
            "either position) AND their strings differ in exactly one position. Return "
            "the maximum total points achievable with optimal play."
        ),
        "test_code": """
assert maxScore(["aa","ab","ba","xx"], "x") == 0   # only one card contains x
assert maxScore(["xa","xb","xc"], "x") == 1        # K3 -> matching 1
assert maxScore(["xa","xb","xc","xd"], "x") == 2   # K4 -> matching 2
assert maxScore(["ax","bx","xa","xb"], "x") == 2   # {ax,bx} and {xa,xb}
assert maxScore(["xx","xa","ax"], "x") == 1        # xx pairs with only one
""",
    },
    {
        "id": "c5_balanced_swap",
        "level": "contest",
        "prompt": (
            "Write a Python function `maxBalancedSubstring(s: str) -> int`. s is a "
            "binary string of '0' and '1'. A string is balanced if it has an equal "
            "number of '0's and '1's. You may perform at most one swap between any two "
            "characters of s, then select a contiguous balanced substring. Return the "
            "maximum possible length of such a balanced substring (0 if none exists)."
        ),
        "test_code": """
def _best(t):
    n = len(t)
    b = 0
    for i in range(n):
        c0 = c1 = 0
        for j in range(i, n):
            if t[j] == '0':
                c0 += 1
            else:
                c1 += 1
            if c0 == c1:
                b = max(b, j - i + 1)
    return b

def _oracle(s):
    ans = _best(s)
    a = list(s)
    n = len(a)
    for i in range(n):
        for j in range(i + 1, n):
            a[i], a[j] = a[j], a[i]
            ans = max(ans, _best(''.join(a)))
            a[i], a[j] = a[j], a[i]
    return ans

for _s in ["01", "0000", "1100", "010", "0111000", "1010010", "00110", "11110000", "1", ""]:
    assert maxBalancedSubstring(_s) == _oracle(_s), (_s, maxBalancedSubstring(_s), _oracle(_s))
""",
    },
]
