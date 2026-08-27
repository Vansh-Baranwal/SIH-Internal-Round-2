import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean up duplicate / conflicting tailwind classes created by naive regex
    content = content.replace('bg-white text-black hover:bg-zinc-200 hover:bg-zinc-300 text-white', 'bg-zinc-200 hover:bg-white text-black')
    content = content.replace('bg-white text-black hover:bg-zinc-200 text-white', 'bg-zinc-200 hover:bg-white text-black')
    content = content.replace('text-white text-black', 'text-black')
    content = content.replace('text-black text-white', 'text-black')
    content = content.replace('hover:bg-zinc-200 hover:bg-zinc-300', 'hover:bg-zinc-300')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, _, files in os.walk('web/src'):
    for file in files:
        if file.endswith('.tsx'):
            process_file(os.path.join(root, file))

print("Class conflicts resolved!")
