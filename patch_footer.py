import re

with open('web/src/components/layout/Footer.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_footer_logo = '<h2 className="text-zinc-300 font-bold tracking-wide mb-4">LunaDrishti</h2>'
new_footer_logo = '<h2 className="text-2xl font-black tracking-tighter mb-4 uppercase leading-none"><span className="text-white">LUNA</span> <span className="text-transparent [-webkit-text-stroke:1px_white]">DRISHTI</span></h2>'

content = content.replace(old_footer_logo, new_footer_logo)

with open('web/src/components/layout/Footer.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated footer in Footer.tsx!")
