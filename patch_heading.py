import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_heading = """<h1 className="text-7xl lg:text-9xl font-black tracking-tight mb-8 leading-[1.1]">
            <span className="block text-white">Luna</span>
            <span className="block text-blue-500">Drishti</span>
          </h1>"""

new_heading = """<h1 className="text-[5rem] lg:text-[10rem] font-black tracking-tighter mb-8 leading-[0.9] uppercase">
            <span className="block text-white">LUNA</span>
            <span className="block text-transparent [-webkit-text-stroke:2px_white] lg:[-webkit-text-stroke:4px_white]">DRISHTI</span>
          </h1>"""

content = content.replace(old_heading, new_heading)

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated heading in Landing.tsx!")
