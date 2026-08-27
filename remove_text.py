import re

with open('web/src/components/Loader.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the "Initializing Platform" text block
content = re.sub(
    r'<motion\.p[^>]*>\s*Initializing Platform\s*</motion\.p>', 
    '', 
    content, 
    flags=re.DOTALL
)

with open('web/src/components/Loader.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed 'Initializing Platform' from Loader.tsx!")
