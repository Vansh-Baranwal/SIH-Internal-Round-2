import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Modify LabelBox component to make `sub` optional and adjust layout dynamically
old_labelbox = """const LabelBox = ({ x, y, title, sub, width=110 }: {x:number, y:number, title:string, sub:string, width?:number}) => (
  <g transform={`translate(${x}, ${y})`}>
    <rect x="0" y="0" width={width} height="40" fill="#09090b" stroke="#3f3f46" strokeWidth="1.5" rx="6" />
    <text x="10" y="16" fill="#f4f4f5" fontSize="11" fontWeight="bold" fontFamily="sans-serif">{title}</text>
    <text x="10" y="30" fill="#a1a1aa" fontSize="10" fontFamily="sans-serif">{sub}</text>
  </g>
);"""

new_labelbox = """const LabelBox = ({ x, y, title, sub, width=110 }: {x:number, y:number, title:string, sub?:string, width?:number}) => (
  <g transform={`translate(${x}, ${y})`}>
    <rect x="0" y="0" width={width} height={sub ? "40" : "28"} fill="#09090b" stroke="#3f3f46" strokeWidth="1.5" rx="6" />
    <text x="10" y={sub ? "16" : "18"} fill="#f4f4f5" fontSize="11" fontWeight="bold" fontFamily="sans-serif">{title}</text>
    {sub && <text x="10" y="30" fill="#a1a1aa" fontSize="10" fontFamily="sans-serif">{sub}</text>}
  </g>
);"""

content = content.replace(old_labelbox, new_labelbox)

# Remove the 'sub' prop from the Lunar Orbit labels
content = content.replace('<LabelBox x="20" y="140" title="Lunar Orbit 1" sub="~ 33 Hours" width={110} />', '<LabelBox x="20" y="140" title="Lunar Orbit 1" width={95} />')
content = content.replace('<LabelBox x="120" y="320" title="Lunar Orbit 2" sub="up to 35 Days" width={115} />', '<LabelBox x="120" y="320" title="Lunar Orbit 2" width={95} />')
content = content.replace('<LabelBox x="290" y="470" title="Lunar Orbit 3" sub="~ 48 hours" width={110} />', '<LabelBox x="290" y="470" title="Lunar Orbit 3" width={95} />')

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed sub titles!")
