import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Tailwind classes
    content = re.sub(r'text-blue-\d+', 'text-zinc-300', content)
    content = re.sub(r'bg-blue-600', 'bg-white text-black hover:bg-zinc-200', content)
    content = re.sub(r'bg-blue-500(\/[1-9]0?)?', 'bg-zinc-300', content)
    content = re.sub(r'hover:bg-blue-500', 'hover:bg-zinc-200', content)
    content = re.sub(r'border-blue-\d+(\/[1-9]0?)?', 'border-white/20', content)
    content = re.sub(r'shadow-blue-\d+(\/[1-9]0?)?', 'shadow-white/10', content)
    content = re.sub(r'accent-blue-\d+', 'accent-zinc-300', content)
    content = re.sub(r'text-rose-500', 'text-zinc-400', content)
    content = re.sub(r'border-t-blue-\d+', 'border-t-white', content)
    
    # Specific Hex colors used in OrbitalPlanner for SVG (removing all blues, greens, reds)
    content = content.replace('#1d4ed8', '#52525b') # solar panels
    content = content.replace('#3b82f6', '#71717a')
    content = content.replace('#60a5fa', '#3f3f46') # landing zone
    content = content.replace('#10b981', '#e4e4e7') # green trajectories -> white/light-gray
    content = content.replace('#ef4444', '#a1a1aa') # red delta v -> gray
    
    # Selection color in Layout.tsx
    content = content.replace('selection:bg-blue-900/50', 'selection:bg-white/20')
    content = content.replace('selection:text-blue-100', 'selection:text-white')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, _, files in os.walk('web/src'):
    for file in files:
        if file.endswith('.tsx'):
            process_file(os.path.join(root, file))

print("Monochrome sweep complete!")
