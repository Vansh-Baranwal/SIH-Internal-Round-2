import re

with open('web/src/pages/Imagery.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("Original Orbital Telemetry (32m/px)", "Original Orbital Telemetry")
content = content.replace("Phase II: Super Resolution (1m/px)", "Phase II: Super Resolution")

with open('web/src/pages/Imagery.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed resolution labels!")
