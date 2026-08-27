import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the invalid backslashes injected by the previous script
content = content.replace(r'rotate\(-15 280 350\)', 'rotate(-15 280 350)')
content = content.replace(r'rotate\(-10 340 350\)', 'rotate(-10 340 350)')
content = content.replace(r'rotate\(-5 400 350\)', 'rotate(-5 400 350)')
content = content.replace(r'onClick=\{handleOrbitClick\}', 'onClick={handleOrbitClick}')
content = content.replace(r'onClick=\{(e) => handleOrbitClick(e, 1)\}', 'onClick={(e) => handleOrbitClick(e, 1)}')
content = content.replace(r'onClick=\{(e) => handleOrbitClick(e, 2)\}', 'onClick={(e) => handleOrbitClick(e, 2)}')
content = content.replace(r'onClick=\{(e) => handleOrbitClick(e, 3)\}', 'onClick={(e) => handleOrbitClick(e, 3)}')

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed syntax errors!")
