import re

with open('web/src/pages/Imagery.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

bad_classes = "file:bg-zinc-300 file:text-zinc-300 hover:file:bg-zinc-300"
good_classes = "file:bg-zinc-200 file:text-black hover:file:bg-white transition-colors"

content = content.replace(bad_classes, good_classes)

with open('web/src/pages/Imagery.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed file input visibility!")
