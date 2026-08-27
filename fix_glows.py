import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix the broken ambient glows
    content = content.replace('bg-white text-black hover:bg-zinc-200/5', 'bg-white/5')
    content = content.replace('bg-white text-black hover:bg-zinc-200/10', 'bg-white/5')
    
    # Also strip purple and indigo glows to make it strictly monochrome
    content = re.sub(r'bg-purple-\d+/\d+', 'bg-white/5', content)
    content = re.sub(r'bg-indigo-\d+/\d+', 'bg-white/5', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, _, files in os.walk('web/src'):
    for file in files:
        if file.endswith('.tsx'):
            process_file(os.path.join(root, file))

print("Fixed broken background glows!")
