"""Dry-run task set: 8 small Python coding problems across difficulty levels.

Each task asks the model to implement a function with a fixed signature.
Success is checked objectively by running `test_code` against the model's
output in a subprocess -- no human judgment, no LLM judge.

Keep tasks small so the dry run stays cheap and fast.
"""

TASKS = [
    # ---- easy ----
    {
        "id": "e1_reverse_words",
        "level": "easy",
        "prompt": (
            "Write a Python function `reverse_words(s: str) -> str` that reverses "
            "the order of words in a string. Words are separated by single spaces. "
            "Leading/trailing spaces should be stripped in the output."
        ),
        "test_code": """
assert reverse_words("hello world") == "world hello"
assert reverse_words("  the quick brown fox ") == "fox brown quick the"
assert reverse_words("single") == "single"
assert reverse_words("") == ""
""",
    },
    {
        "id": "e2_fizzbuzz",
        "level": "easy",
        "prompt": (
            "Write a Python function `fizzbuzz(n: int) -> list[str]` that returns a "
            "list of strings for 1..n inclusive. Multiples of 3 -> 'Fizz', multiples "
            "of 5 -> 'Buzz', multiples of both -> 'FizzBuzz', otherwise the number as "
            "a string."
        ),
        "test_code": """
assert fizzbuzz(1) == ["1"]
assert fizzbuzz(5) == ["1", "2", "Fizz", "4", "Buzz"]
assert fizzbuzz(15)[-1] == "FizzBuzz"
assert fizzbuzz(15)[2] == "Fizz"
""",
    },
    {
        "id": "e3_is_palindrome",
        "level": "easy",
        "prompt": (
            "Write a Python function `is_palindrome(s: str) -> bool` that returns True "
            "if the string is a palindrome considering only alphanumeric characters and "
            "ignoring case."
        ),
        "test_code": """
assert is_palindrome("A man, a plan, a canal: Panama") is True
assert is_palindrome("race a car") is False
assert is_palindrome("") is True
assert is_palindrome(".,") is True
""",
    },
    # ---- medium ----
    {
        "id": "m1_merge_intervals",
        "level": "medium",
        "prompt": (
            "Write a Python function `merge_intervals(intervals: list[list[int]]) -> "
            "list[list[int]]` that merges all overlapping intervals and returns them "
            "sorted by start. Example: [[1,3],[2,6],[8,10],[15,18]] -> "
            "[[1,6],[8,10],[15,18]]."
        ),
        "test_code": """
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([]) == []
assert merge_intervals([[1,4],[0,4]]) == [[0,4]]
""",
    },
    {
        "id": "m2_group_anagrams",
        "level": "medium",
        "prompt": (
            "Write a Python function `group_anagrams(words: list[str]) -> "
            "list[list[str]]` that groups words that are anagrams of each other. "
            "Each group's words should preserve input order, and groups should be "
            "sorted by their first-appearing member's original index."
        ),
        "test_code": """
r = group_anagrams(["eat","tea","tan","ate","nat","bat"])
# normalize for comparison: each group as a set, whole thing as set of frozensets
got = {frozenset(g) for g in r}
exp = {frozenset(["eat","tea","ate"]), frozenset(["tan","nat"]), frozenset(["bat"])}
assert got == exp, r
assert group_anagrams([]) == []
""",
    },
    {
        "id": "m3_roman_to_int",
        "level": "medium",
        "prompt": (
            "Write a Python function `roman_to_int(s: str) -> int` that converts a "
            "Roman numeral string (I, V, X, L, C, D, M) to an integer. Handle "
            "subtractive cases like IV=4, IX=9, XL=40, CM=900."
        ),
        "test_code": """
assert roman_to_int("III") == 3
assert roman_to_int("IV") == 4
assert roman_to_int("IX") == 9
assert roman_to_int("LVIII") == 58
assert roman_to_int("MCMXCIV") == 1994
""",
    },
    # ---- hard ----
    {
        "id": "h1_word_break",
        "level": "hard",
        "prompt": (
            "Write a Python function `word_break(s: str, words: list[str]) -> bool` "
            "that returns True if s can be segmented into a space-separated sequence "
            "of one or more dictionary words (words may be reused)."
        ),
        "test_code": """
assert word_break("leetcode", ["leet","code"]) is True
assert word_break("applepenapple", ["apple","pen"]) is True
assert word_break("catsandog", ["cats","dog","sand","and","cat"]) is False
assert word_break("aaaaaaa", ["aaaa","aaa"]) is True
""",
    },
    {
        "id": "h2_lru_cache",
        "level": "hard",
        "prompt": (
            "Implement a Python class `LRUCache` with `__init__(self, capacity: int)`, "
            "`get(self, key: int) -> int` (returns -1 if absent), and "
            "`put(self, key: int, value: int) -> None`. When capacity is exceeded, "
            "evict the least recently used item. get and put both count as uses."
        ),
        "test_code": """
c = LRUCache(2)
c.put(1, 1)
c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)          # evicts key 2
assert c.get(2) == -1
c.put(4, 4)          # evicts key 1
assert c.get(1) == -1
assert c.get(3) == 3
assert c.get(4) == 4
""",
    },
    # ---- expert: algorithmically hard or fiddly-spec (meant to trip the cheap model) ----
    {
        "id": "x1_regex_match",
        "level": "expert",
        "prompt": (
            "Write a Python function `is_match(s: str, p: str) -> bool` implementing "
            "regular expression matching where '.' matches any single character and "
            "'*' matches zero or more of the PRECEDING element. The match must cover "
            "the ENTIRE input string."
        ),
        "test_code": """
assert is_match("aa", "a") is False
assert is_match("aa", "a*") is True
assert is_match("ab", ".*") is True
assert is_match("aab", "c*a*b") is True
assert is_match("mississippi", "mis*is*p*.") is False
assert is_match("mississippi", "mis*is*ip*.") is True
""",
    },
    {
        "id": "x2_min_window",
        "level": "expert",
        "prompt": (
            "Write a Python function `min_window(s: str, t: str) -> str` returning the "
            "minimum-length substring of s that contains every character of t including "
            "duplicates (counting multiplicity). Return '' if no such window exists. "
            "If multiple minimum windows exist, any one is acceptable."
        ),
        "test_code": """
assert min_window("ADOBECODEBANC", "ABC") == "BANC"
assert min_window("a", "a") == "a"
assert min_window("a", "aa") == ""
assert min_window("aa", "aa") == "aa"
""",
    },
    {
        "id": "x3_text_justify",
        "level": "expert",
        "prompt": (
            "Write a Python function `full_justify(words: list[str], maxWidth: int) -> "
            "list[str]`. Pack words greedily into lines of exactly maxWidth characters, "
            "fully justified: distribute extra spaces between words, with more spaces "
            "going to the LEFT gaps when they don't divide evenly. The LAST line (and "
            "any line with a single word) is LEFT-justified: single spaces between "
            "words, padded with trailing spaces to maxWidth."
        ),
        "test_code": """
assert full_justify(
    ["This","is","an","example","of","text","justification."], 16
) == ["This    is    an", "example  of text", "justification.  "]
assert full_justify(
    ["What","must","be","acknowledgment","shall","be"], 16
) == ["What   must   be", "acknowledgment  ", "shall be        "]
""",
    },
    {
        "id": "x4_number_to_words",
        "level": "expert",
        "prompt": (
            "Write a Python function `number_to_words(num: int) -> str` that converts a "
            "non-negative integer to its English words representation. Words are "
            "space-separated with each word capitalized (e.g. 'One Hundred Twenty "
            "Three'). No leading/trailing spaces, no 'and'."
        ),
        "test_code": """
assert number_to_words(0) == "Zero"
assert number_to_words(100) == "One Hundred"
assert number_to_words(123) == "One Hundred Twenty Three"
assert number_to_words(12345) == "Twelve Thousand Three Hundred Forty Five"
assert number_to_words(1000000) == "One Million"
assert number_to_words(1234567) == (
    "One Million Two Hundred Thirty Four Thousand Five Hundred Sixty Seven"
)
""",
    },
    {
        "id": "x5_calculator",
        "level": "expert",
        "prompt": (
            "Write a Python function `calculate(s: str) -> int` that evaluates a string "
            "arithmetic expression containing non-negative integers and the operators "
            "+, -, *, / separated by optional spaces (no parentheses). Multiplication "
            "and division have higher precedence. Integer division truncates toward "
            "zero."
        ),
        "test_code": """
assert calculate("3+2*2") == 7
assert calculate(" 3/2 ") == 1
assert calculate(" 3+5 / 2 ") == 5
assert calculate("14-3/2") == 13
assert calculate("2*3+4*5") == 26
""",
    },
    {
        "id": "x6_edit_distance",
        "level": "expert",
        "prompt": (
            "Write a Python function `min_distance(a: str, b: str) -> int` returning the "
            "minimum number of single-character insertions, deletions, or "
            "substitutions needed to transform a into b (Levenshtein distance)."
        ),
        "test_code": """
assert min_distance("horse", "ros") == 3
assert min_distance("intention", "execution") == 5
assert min_distance("", "abc") == 3
assert min_distance("abc", "abc") == 0
""",
    },
    {
        "id": "x7_decode_ways",
        "level": "expert",
        "prompt": (
            "Write a Python function `num_decodings(s: str) -> int` returning the number "
            "of ways to decode a digit string, where '1'->'A', ..., '26'->'Z'. A '0' "
            "cannot start a code and has no standalone mapping. Return 0 for invalid "
            "strings."
        ),
        "test_code": """
assert num_decodings("12") == 2
assert num_decodings("226") == 3
assert num_decodings("0") == 0
assert num_decodings("06") == 0
assert num_decodings("100") == 0
assert num_decodings("101") == 1
assert num_decodings("2101") == 1
""",
    },
    {
        "id": "x8_trap_rain",
        "level": "expert",
        "prompt": (
            "Write a Python function `trap(height: list[int]) -> int` that, given a list "
            "of non-negative bar heights each of width 1, computes how much rainwater "
            "can be trapped between the bars after raining."
        ),
        "test_code": """
assert trap([0,1,0,2,1,0,1,3,2,1,2,1]) == 6
assert trap([4,2,0,3,2,5]) == 9
assert trap([]) == 0
assert trap([1,2,3]) == 0
""",
    },
]
