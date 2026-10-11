# valohai-yaml: a duration ending in a bare number raises IndexError

`parse_duration_string` in [valohai/valohai-yaml](https://github.com/valohai/valohai-yaml)
builds its match with an optional suffix group and then indexes that group
without checking it is there. Two things come out of it:

1. Any duration string that ends in a number with no unit raises
   **`IndexError: string index out of range`**, not this module's own
   `ValueError`. `"1h30"`, a typo for `1h30m`, is enough to trigger it, as is
   `"3600"`, which is what you get when a number is quoted in `valohai.yaml`.
2. Only the **first letter** of the suffix is read, so every unit beginning
   with `m` becomes minutes. `time-limit: 1month` is read as one minute, so a
   step is killed after 60 seconds instead of running for a month.

Both are reachable from `valohai.yaml` through `time-limit` and
`no-output-timeout` ([`step.py` lines 95 to 97](https://github.com/valohai/valohai-yaml/blob/master/valohai_yaml/objs/step.py#L95-L97)).

Reported upstream as [valohai/valohai-yaml#227](https://github.com/valohai/valohai-yaml/issues/227).

## The code

[`valohai_yaml/utils/duration.py`](https://github.com/valohai/valohai-yaml/blob/master/valohai_yaml/utils/duration.py):

```python
simple_duration_re = re.compile(r"(?P<value>[.\d]+)\s*(?P<suffix>[a-z]*)")

def parse_duration_string(duration_str: str) -> datetime.timedelta:
    total_duration_sec = 0.0
    for match in simple_duration_re.finditer(duration_str):
        value = float(match.group("value"))
        suffix = match.group("suffix").lower()
        if suffix[0] not in suffixes:        # <-- suffix can be ""
            raise ValueError(f"Unknown duration suffix in {match.group(0)!r}")
        total_duration_sec += value * suffixes[suffix[0]]
```

The suffix group is `[a-z]*`, zero or more. A bare number matches it as the
empty string, and `suffix[0]` then raises.

## Defect 1: IndexError on a trailing bare number

| input | result |
| --- | --- |
| `"1h30m"` | 1:10:00 equivalent, works |
| `"3600"` | **IndexError** |
| `"1h30"` | **IndexError** |
| `"1h 30"` | **IndexError** |
| `"2w 5"` | **IndexError** |
| `"1.5"` | **IndexError** |
| `3600` as an int | 1:00:00, works |

The last row is the awkward part. The same number is fine as an `int` and
raises as a `str`, so quoting a value in YAML changes a working config into a
crash.

Because the exception is `IndexError` rather than `ValueError`, a caller
written as `except ValueError:` around duration parsing does not catch it. The
project already treats this distinction as worth fixing: PR #112,
"Validating empty values as int/float gives more specific error", did the same
kind of tidying elsewhere.

## Defect 2: every unit starting with m is minutes

| input | read as | meant |
| --- | --- | --- |
| `1s`, `1sec` | 1 second | 1 second |
| `1m`, `1min`, `1mins` | 1 minute | 1 minute |
| `1h`, `1hr` | 1 hour | 1 hour |
| `1d`, `1day` | 1 day | 1 day |
| `1w`, `1week` | 1 week | 1 week |
| `1month` | **1 minute** | 1 month |
| `1mo` | **1 minute** | 1 month |

Loose prefix matching is clearly deliberate: the project's own test asserts
that `"1.5d 2hörs"` parses as days and hours. So `1mins` working is by design.
The `month` collision looks like a side effect of that rather than a decision,
and it fails in the dangerous direction, cutting a limit by a factor of 43,200
instead of raising.

This repository does not try to fix defect 2, because any fix changes
documented behaviour. It is reported so the project can decide.

## The patch

`fix.patch` adds a guard for the empty suffix. Nine lines, most of it comment,
in one file:

```python
if not suffix:
    raise ValueError(
        f"Missing duration suffix in {match.group(0)!r}; "
        f"expected one of {''.join(sorted(suffixes))}"
    )
```

Result:

| input | before | after |
| --- | --- | --- |
| `"3600"` | `IndexError: string index out of range` | `ValueError: Missing duration suffix in '3600'; expected one of dhmsw` |
| `"1h30"` | `IndexError: string index out of range` | `ValueError: Missing duration suffix in '30'; expected one of dhmsw` |

The patch does not guess a unit for a bare number. Defaulting to seconds would
line the string path up with the int path, which is tempting, but it would also
make `"1h30"` quietly mean one hour and thirty seconds when `1h30m` was meant.
Raising is the safer of the two. The choice is worth a maintainer's opinion
either way.

### Effect on existing behaviour

All eight cases in `tests/test_duration_parsing.py` still pass, including
`"1.5d 2hörs"`:

```
PASS  '60 minutes  '   expected 1:00:00           got 1:00:00
PASS  '1h10m'          expected 1:10:00           got 1:10:00
PASS  '2w'             expected 14 days, 0:00:00  got 14 days, 0:00:00
PASS  '1.5d'           expected 1 day, 12:00:00   got 1 day, 12:00:00
PASS  '1.5d 2hörs'     expected 1 day, 14:00:00   got 1 day, 14:00:00
PASS  ''               expected None              got None
PASS  '   '            expected None              got None
PASS  72               expected 0:01:12           got 0:01:12
```

## Reproducing

Nothing to install. The script carries a verbatim copy of the function:

```bash
python verify.py
```

To run it against the real module in a checkout, which is what actually proves
the point:

```bash
git clone https://github.com/valohai/valohai-yaml
python verify.py --src ./valohai-yaml
```

It loads `valohai_yaml/utils/duration.py` by file path rather than importing
the package, so neither `jsonschema` nor `leval` is needed. `RESULTS.txt` is
the saved output of that second form, run against `ca37e9e`.

To apply the patch:

```bash
git apply fix.patch
```

## Files

| file | what it is |
| --- | --- |
| `verify.py` | all four checks, no dependencies |
| `RESULTS.txt` | saved output, run against the real module at `ca37e9e` |
| `fix.patch` | the nine line patch |

## Licence

MIT, matching valohai-yaml. The `shipped_parse_duration_string` function in
`verify.py` is copied verbatim from valohai-yaml, Copyright Valohai, MIT.
