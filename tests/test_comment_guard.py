"""Check the comment guard's PowerShell comment stripping.

    python tests/test_comment_guard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from comment_guard import ps1_check, ps1_code  # noqa: E402

# A comment starts at a token boundary.
assert ps1_code("$x = 1 # note") == ["$x = 1"]
assert ps1_code("foo;#note") == ["foo;"]
assert ps1_code("# whole-line comment") == []
assert ps1_code("<# block #> $y = 2") == [" $y = 2"]
# A # inside a token or a string is code.
assert ps1_code("Write-Host a#b") == ["Write-Host a#b"]
assert ps1_code("Invoke-WebRequest https://x/#frag") == ["Invoke-WebRequest https://x/#frag"]
assert ps1_code('Write-Host "a # b"') == ['Write-Host "a # b"']

# Changing code after a mid-token # is a code change, so the guard must fail.
try:
    ps1_check("Write-Host a#b\n", "Write-Host a#c\n")
except SystemExit as e:
    assert e.code == 1
else:
    raise AssertionError("guard passed a code change after a mid-token #")

# Changing only a real comment passes.
ps1_check("$x = 1 # old\n", "$x = 1 # new\n")
print("comment_guard: all checks passed")
