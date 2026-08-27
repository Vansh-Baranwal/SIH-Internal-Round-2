import re

with open('web/src/components/layout/Navbar.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Search from imports
content = content.replace('import { Database, Satellite, Search } from \'lucide-react\';', 'import { Database, Satellite } from \'lucide-react\';')

# 2. Remove Search icon element
content = re.sub(r'<Search className="[^"]+" />\s*', '', content)

# 3. Change awaiting data colors to black
content = content.replace("hasData ? 'text-green-500' : 'text-amber-500'", "hasData ? 'text-black' : 'text-black'")
content = content.replace("hasData ? 'text-green-600' : 'text-amber-600'", "hasData ? 'text-black' : 'text-black'")

with open('web/src/components/layout/Navbar.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated Navbar.tsx!")
