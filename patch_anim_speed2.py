import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Tweak to 0.15 instead of 0.25 for a balanced cinematic pacing
content = content.replace('staggerChildren: 0.25', 'staggerChildren: 0.15')

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Balanced the stagger speed.")
