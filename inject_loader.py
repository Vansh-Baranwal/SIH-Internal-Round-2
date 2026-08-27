import re

with open('web/src/components/layout/Layout.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("import { Footer } from './Footer';", "import { Footer } from './Footer';\nimport { AppLoader } from '../Loader';")
content = content.replace("<Navbar />", "<AppLoader />\n      <Navbar />")

with open('web/src/components/layout/Layout.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added AppLoader to Layout!")
