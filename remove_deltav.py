import re

with open('web/src/pages/Trajectory.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Change the grid to 1 col
content = content.replace('<div className="grid grid-cols-1 md:grid-cols-2 gap-16 mb-20">', '<div className="grid grid-cols-1 gap-16 mb-20">')

# Remove the Delta-V budget section
pattern = r'<div className="border-l border-white/5 pl-8">\s*<h2 className="text-zinc-300 font-bold tracking-widest uppercase mb-10 text-xs">Delta-V Budget</h2>.*?</svg>\s*</div>'
# wait, it's not svg, it's:
old_block = """        <div className="border-l border-white/5 pl-8">
            <h2 className="text-zinc-300 font-bold tracking-widest uppercase mb-10 text-xs">Delta-V Budget</h2>
            <div className="flex flex-col items-start justify-center h-full pb-8">
                <div className="text-[10px] text-zinc-600 font-bold tracking-widest uppercase mb-2">Propellant Margin</div>
                <div className="text-6xl font-light text-white font-mono tracking-tight">
                    {m6?.trajectory?.propellant_margin || 0}<span className="text-2xl text-zinc-600 ml-1">%</span>
                </div>
                <div className="mt-8 text-xs text-green-500 font-bold tracking-widest uppercase">
                    Sufficient fuel for landing and hazard avoidance.
                </div>
            </div>
        </div>"""

content = content.replace(old_block, "")

with open('web/src/pages/Trajectory.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed Delta-V budget!")
