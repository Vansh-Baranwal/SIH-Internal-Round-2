import re

with open('web/src/components/HUD.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the PROPELLANT MARGIN block
pattern = r'<div className="mb-4">\s*<div className="text-\[10px\] text-zinc-500 font-medium mb-1">PROPELLANT MARGIN</div>\s*<div className="text-xl text-white font-light font-mono tracking-tight">14\.2<span className="text-xs text-zinc-600 ml-1">%</span></div>\s*</div>'
content = re.sub(pattern, '', content)

with open('web/src/components/HUD.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed Propellant Margin from HUD!")
