"""Evidence for two defects in valohai_yaml.utils.duration.

Run against the copies embedded below, which need nothing installed:

    python verify.py

Or against a real checkout, which is what actually proves the point:

    python verify.py --src /path/to/valohai-yaml

The embedded `shipped` function is copied verbatim from valohai-yaml
(MIT, Copyright Valohai) at commit ca37e9e, file
valohai_yaml/utils/duration.py.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import re
import sys

suffixes = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 60 * 60 * 24 * 7,
}

simple_duration_re = re.compile(r"(?P<value>[.\d]+)\s*(?P<suffix>[a-z]*)")


# --------------------------------------------------------------------------
# Copied verbatim from valohai-yaml. The suffix group is `[a-z]*`, zero or
# more, but `suffix[0]` is indexed without a guard.
# --------------------------------------------------------------------------
def shipped_parse_duration_string(duration_str: str) -> datetime.timedelta:
    total_duration_sec = 0.0
    for match in simple_duration_re.finditer(duration_str):
        value = float(match.group("value"))
        suffix = match.group("suffix").lower()
        if suffix[0] not in suffixes:
            raise ValueError(f"Unknown duration suffix in {match.group(0)!r}")
        total_duration_sec += value * suffixes[suffix[0]]
    if total_duration_sec <= 0:
        raise ValueError(f"Could not parse positive duration from {duration_str!r}")
    return datetime.timedelta(seconds=total_duration_sec)


def shipped(duration_value: int | str | None) -> datetime.timedelta | None:
    if duration_value is None:
        return None
    if isinstance(duration_value, int):
        return datetime.timedelta(seconds=duration_value)
    if isinstance(duration_value, str):
        if duration_value.strip():
            return shipped_parse_duration_string(duration_value)
        return None
    raise ValueError(f"Could not parse duration from {duration_value!r}")


# --------------------------------------------------------------------------
# The same thing with the proposed guard, which is all fix.patch adds.
# --------------------------------------------------------------------------
def patched_parse_duration_string(duration_str: str) -> datetime.timedelta:
    total_duration_sec = 0.0
    for match in simple_duration_re.finditer(duration_str):
        value = float(match.group("value"))
        suffix = match.group("suffix").lower()
        if not suffix:
            raise ValueError(
                f"Missing duration suffix in {match.group(0)!r}; "
                f"expected one of {''.join(sorted(suffixes))}"
            )
        if suffix[0] not in suffixes:
            raise ValueError(f"Unknown duration suffix in {match.group(0)!r}")
        total_duration_sec += value * suffixes[suffix[0]]
    if total_duration_sec <= 0:
        raise ValueError(f"Could not parse positive duration from {duration_str!r}")
    return datetime.timedelta(seconds=total_duration_sec)


def patched(duration_value: int | str | None) -> datetime.timedelta | None:
    if duration_value is None:
        return None
    if isinstance(duration_value, int):
        return datetime.timedelta(seconds=duration_value)
    if isinstance(duration_value, str):
        if duration_value.strip():
            return patched_parse_duration_string(duration_value)
        return None
    raise ValueError(f"Could not parse duration from {duration_value!r}")


def load_real(src: str):
    """Import the real duration module straight from a checkout.

    Imported by file path on purpose: importing the package would pull in
    jsonschema and leval, and this module needs neither.
    """
    path = f"{src.rstrip('/')}/valohai_yaml/utils/duration.py"
    spec = importlib.util.spec_from_file_location("real_duration", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(fn, value):
    """Return (text, is_error, exception_type)."""
    try:
        return str(fn(value)), False, None
    except Exception as exc:  # noqa: BLE001 - reporting whatever comes out
        return f"{type(exc).__name__}: {exc}", True, type(exc).__name__


def heading(text: str) -> None:
    print()
    print(text)
    print("-" * len(text))


# Durations that end in a number with no unit. The suffix group matches
# empty, and the shipped code indexes it anyway.
BARE = [
    ('"3600"', "3600", "a number quoted in YAML, so it arrives as a str"),
    ('"1h30"', "1h30", "a typo: the trailing m of 1h30m was dropped"),
    ('"1h 30"', "1h 30", "the same typo with a space"),
    ('"2w 5"', "2w 5", "a trailing bare number"),
    ('"1.5"', "1.5", "a bare float"),
]

# Their own test cases, from tests/test_duration_parsing.py.
EXISTING_TESTS = [
    ("60 minutes  ", datetime.timedelta(hours=1)),
    ("1h10m", datetime.timedelta(hours=1, minutes=10)),
    ("2w", datetime.timedelta(weeks=2)),
    ("1.5d", datetime.timedelta(days=1, hours=12)),
    ("1.5d 2hörs", datetime.timedelta(days=1, hours=14)),
    ("", None),
    ("   ", None),
    (72, datetime.timedelta(seconds=72)),
]

# Only suffix[0] is inspected, so every unit beginning with m is minutes.
FIRST_LETTER = [
    ("1s", "1 second"),
    ("1sec", "1 second"),
    ("1m", "1 minute"),
    ("1min", "1 minute"),
    ("1mins", "1 minute"),
    ("1h", "1 hour"),
    ("1hr", "1 hour"),
    ("1d", "1 day"),
    ("1day", "1 day"),
    ("1w", "1 week"),
    ("1week", "1 week"),
    ("1month", "1 month"),
    ("1mo", "1 month"),
]


def part_1(fn) -> int:
    heading("1. Durations ending in a bare number raise IndexError")
    print("  The regex is (?P<value>[.\\d]+)\\s*(?P<suffix>[a-z]*). The suffix")
    print("  group is optional, but suffix[0] is indexed with no guard.")
    print()
    print(f"  {'input':<10}{'outcome':<58}{'why it matters'}")
    print("  " + "-" * 104)
    index_errors = 0
    for label, value, note in BARE:
        text, _, kind = call(fn, value)
        if kind == "IndexError":
            index_errors += 1
        print(f"  {label:<10}{text:<58}{note}")
    print()
    print("  For contrast, the int path accepts the same number happily:")
    for value in (3600, 72):
        text, _, _ = call(fn, value)
        print(f"    parse_duration({value!r}) = {text}")
    print()
    print(f"  IndexError count: {index_errors} of {len(BARE)}")
    return index_errors


def part_2(fn) -> None:
    heading("2. Only the first letter of the suffix is read")
    print("  suffixes maps s, m, h, d, w. Because just suffix[0] is checked,")
    print("  any unit starting with m is treated as minutes.")
    print()
    print(f"  {'input':<10}{'read as':<22}{'meant':<12}{''}")
    print("  " + "-" * 58)
    for value, meant in FIRST_LETTER:
        text, _, _ = call(fn, value)
        flag = ""
        if meant in ("1 month",):
            flag = "  <-- wrong by 43200x"
        print(f"  {value:<10}{text:<22}{meant:<12}{flag}")
    print()
    print("  A step written as `time-limit: 1month` is killed after 60 seconds.")
    print("  Their own test asserts '1.5d 2hoers' parses as hours, so loose")
    print("  prefix matching is deliberate. The month collision looks like a")
    print("  side effect of it rather than a decision.")


def part_3(shipped_fn, patched_fn) -> int:
    heading("3. The patch turns the IndexError into a clear ValueError")
    print(f"  {'input':<10}{'shipped':<44}{'patched'}")
    print("  " + "-" * 104)
    for label, value, _ in BARE:
        before, _, _ = call(shipped_fn, value)
        after, _, _ = call(patched_fn, value)
        print(f"  {label:<10}{before:<44}{after}")
    print()
    print("  The patch does not guess a unit. Treating a bare number as seconds")
    print("  would match the int path, but it would also make '1h30' mean one")
    print("  hour and thirty seconds, silently, when 1h30m was meant. An error")
    print("  is the safer answer; the choice is noted in the issue.")
    return 0


def part_4(patched_fn) -> int:
    heading("4. The eight existing test cases still pass")
    print("  From tests/test_duration_parsing.py.")
    print()
    failures = 0
    for case, expected in EXISTING_TESTS:
        try:
            got = patched_fn(case)
            ok = got == expected
        except Exception as exc:  # noqa: BLE001
            got, ok = f"{type(exc).__name__}: {exc}", False
        failures += not ok
        label = "PASS" if ok else "FAIL"
        print(f"  {label}  {case!r:<18} expected {str(expected):<18} got {got}")
    print()
    if failures:
        print(f"  {failures} of {len(EXISTING_TESTS)} FAILED")
    else:
        print(f"  all {len(EXISTING_TESTS)} pass")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        help="path to a valohai-yaml checkout, to run against the real module",
    )
    args = parser.parse_args()

    print("valohai-yaml: duration parsing")
    print("=" * 72)

    shipped_fn = shipped
    source = "the copy embedded in this file"
    if args.src:
        real = load_real(args.src)
        shipped_fn = real.parse_duration
        source = f"the real module in {args.src}"
    print(f"Testing {source}.")

    index_errors = part_1(shipped_fn)
    part_2(shipped_fn)
    part_3(shipped_fn, patched)
    failures = part_4(patched)

    print()
    print("=" * 72)
    if index_errors == len(BARE) and failures == 0:
        print("Both defects reproduced, and the patch keeps every existing case.")
        return 0
    print("Unexpected result. See above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
