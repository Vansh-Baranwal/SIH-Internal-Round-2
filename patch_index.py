import re

with open('web/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Update favicon link
content = re.sub(
    r'<link rel="icon" type="image/[^"]+" href="/favicon\.[^"]+" />', 
    '<link rel="icon" type="image/png" href="/favicon.png" />', 
    content
)

# If it didn't find the exact match, let's just do a string replace for the known original
content = content.replace('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />', '<link rel="icon" type="image/png" href="/favicon.png" />')

# Update title
content = re.sub(
    r'<title>.*?</title>', 
    '<title>LUNA DRISHTI</title>', 
    content
)

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated index.html title and favicon!")
