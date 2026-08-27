import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Slow down stagger
content = content.replace('staggerChildren: 0.08', 'staggerChildren: 0.25')

# Slow down letter animation
content = content.replace('duration: 0.6,', 'duration: 1.2,')

# Slow down word animation
content = content.replace('duration: 0.5,', 'duration: 1.0,')

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Slowed down the animations!")
