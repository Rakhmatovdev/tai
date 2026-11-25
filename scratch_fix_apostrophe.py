#!/usr/bin/env python3
"""Fix apostrophe issue in zh quiz note and ja quiz note."""
path = r'brave_language_tutor.py'
content = open(path, encoding='utf-8').read()

# Fix 1: zh quiz note - apostrophe inside single-quoted string
old = "'note': '虽然 (garchi) + 但是 (lekin/ammo) → ziddiyat bog'lovchisi. «虽然很难，但是值得。»',"
new = """'note': "虽然 (garchi) + 但是 (lekin/ammo) → ziddiyat bog'lovchisi. «虽然很难，但是值得。»","""

if old not in content:
    print("ERROR: zh note not found as expected")
    # Show context around line 567
    lines = content.split('\n')
    for i, line in enumerate(lines[560:575], start=561):
        print(f"{i}: {repr(line)}")
else:
    content = content.replace(old, new, 1)
    print("Fixed zh quiz note apostrophe")

open(path, 'w', encoding='utf-8').write(content)
print("Done")
