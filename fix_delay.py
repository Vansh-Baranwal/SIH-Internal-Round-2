import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Change the delay to start exactly after the loader finishes completely
content = content.replace('delay: 2.2, // Wait for global loader to finish', 'delay: 3.0, // Wait for global loader to vanish completely (2.0s wait + 0.8s fade)')

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated animation delay!")
