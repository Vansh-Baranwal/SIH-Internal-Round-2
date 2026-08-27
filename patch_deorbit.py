import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add useRef to imports
content = content.replace("import React, { useState, useMemo } from 'react';", "import React, { useState, useMemo, useRef } from 'react';")

# 2. Add state and ref and click handler
state_block = """
  const [vx, setVx] = useState(0);
  const [vz, setVz] = useState(0);
  const [deorbitPoint, setDeorbitPoint] = useState<{x: number, y: number} | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const handleOrbitClick = (e: React.MouseEvent) => {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const cursorPt = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    setDeorbitPoint({ x: cursorPt.x, y: cursorPt.y });
  };
"""
content = re.sub(r"const \[vx, setVx\] = useState\(0\);\s*const \[vz, setVz\] = useState\(0\);", state_block.strip(), content)

# 3. Add ref to svg
content = content.replace('<svg width="100%" height="100%" viewBox="0 0 600 600" className="absolute inset-0">', '<svg ref={svgRef} width="100%" height="100%" viewBox="0 0 600 600" className="absolute inset-0">')

# 4. Make Orbit 3 interactive
orbit_3_original = '{/* Orbit 3 (Inner) */}\n            <ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="#52525b" strokeWidth="3" />'
orbit_3_new = """{/* Orbit 3 (Inner) */}
            <ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="#52525b" strokeWidth="3" />
            {/* Invisible thicker overlay for easier clicking */}
            <ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={handleOrbitClick} />"""
content = content.replace(orbit_3_original, orbit_3_new)

# 5. Conditional render of green path and marker
old_path_block = r"\{\/\* Deorbit Burn Point on Orbit 3 \*\/\}[\s\S]+?strokeDasharray=\"4 4\"\s*\/>"
new_path_block = """{deorbitPoint && (
              <g>
                {/* Deorbit Burn Point */}
                <g transform={`translate(${deorbitPoint.x}, ${deorbitPoint.y})`}>
                  <circle cx="0" cy="0" r="4" fill="#10b981" />
                  <circle cx="0" cy="0" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
                  <text x="-45" y="-10" fill="#10b981" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>
                </g>
                {/* Final Descent Trajectory (dynamic elliptical arc) */}
                <path 
                  d={`M ${deorbitPoint.x} ${deorbitPoint.y} A 120 100 -5 0 1 ${visualTargetX} ${visualTargetY}`} 
                  fill="none" 
                  stroke="#10b981" 
                  strokeWidth="3" 
                  strokeDasharray="4 4"
                />
              </g>
            )}"""
content = re.sub(old_path_block, new_path_block, content)

# 6. Change Execute button to be disabled if no point is selected
old_button = r"<button \s*onClick=\{\(\) => onExecute\(targetX, targetZ\)\}\s*className=\"w-full py-4 rounded-xl font-semibold tracking-wide text-sm transition-all shadow-lg bg-blue-600 hover:bg-blue-500 text-white\"\s*>\s*Execute Divert Maneuver\s*<\/button>"
new_button = """<button 
            onClick={() => deorbitPoint && onExecute(targetX, targetZ)}
            disabled={!deorbitPoint}
            className={`w-full py-4 rounded-xl font-semibold tracking-wide text-sm transition-all shadow-lg ${deorbitPoint ? 'bg-blue-600 hover:bg-blue-500 text-white' : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'}`}
          >
            {deorbitPoint ? 'Execute Divert Maneuver' : 'Select Deorbit Point First'}
          </button>"""
content = re.sub(old_button, new_button, content)

# 7. Also make Orbit 1 and 2 clickable for ultimate freedom
for rx, ry, rt, cxx, cyy in [("270", "180", "-15", "280", "350"), ("200", "150", "-10", "340", "350")]:
    o_orig = f'<ellipse cx="{cxx}" cy="{cyy}" rx="{rx}" ry="{ry}" transform="rotate({rt} {cxx} {cyy})" fill="none" stroke="#52525b" strokeWidth="3" />'
    o_new = f'{o_orig}\n            <ellipse cx="{cxx}" cy="{cyy}" rx="{rx}" ry="{ry}" transform="rotate({rt} {cxx} {cyy})" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={{handleOrbitClick}} />'
    content = content.replace(o_orig, o_new)

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated interactive deorbit selection!")
