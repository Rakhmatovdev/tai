#!/usr/bin/env python3
"""Fix remaining apostrophe issues in quiz notes."""
path = r'brave_language_tutor.py'
content = open(path, encoding='utf-8').read()

fixes = [
    (
        "'note': '「雨にもかかわらず出かけた」= Yomg'irga qaramasdan chiqib ketdi. C1/N2 darajasi.',",
        '"\'note\': \'「雨にもかかわらず出かけた」= Yomg\\\'irga qaramasdan chiqib ketdi. C1/N2 darajasi.\','
    )
]

# Use a different approach - directly find and replace using the raw bytes
old_ja = "'note': '「雨にもかかわらず出かけた」= Yomg'irga qaramasdan chiqib ketdi. C1/N2 darajasi.',"
new_ja = """'note': "「雨にもかかわらず出かけた」= Yomg'irga qaramasdan chiqib ketdi. C1/N2 darajasi.","""

if old_ja in content:
    content = content.replace(old_ja, new_ja, 1)
    print("Fixed ja quiz note apostrophe")
else:
    print("ja note not found, checking context:")
    for i, line in enumerate(content.split('\n')[570:580], start=571):
        print(f"{i}: {repr(line)}")

open(path, 'w', encoding='utf-8').write(content)
print("Done")
