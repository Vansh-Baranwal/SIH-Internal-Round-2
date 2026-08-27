import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the state and click handler to accept orbitIndex
state_block = """
  const [vx, setVx] = useState(0);
  const [vz, setVz] = useState(0);
  const [deorbitData, setDeorbitData] = useState<{x: number, y: number, orbit: number} | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const handleOrbitClick = (e: React.MouseEvent, orbitIndex: number) => {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const cursorPt = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    setDeorbitData({ x: cursorPt.x, y: cursorPt.y, orbit: orbitIndex });
  };
"""

content = re.sub(
    r"const \[vx, setVx\] = useState\(0\);\s*const \[vz, setVz\] = useState\(0\);\s*const \[deorbitPoint, setDeorbitPoint\] = useState.*?;\s*const svgRef = useRef.*?;\s*const handleOrbitClick = \(e: React\.MouseEvent\) => \{.*?\};\s*",
    state_block.strip() + "\n",
    content,
    flags=re.DOTALL
)

# 2. Add the dynamic path generator logic inside the component render
dynamic_path_logic = """
  // Generate multi-stage spiral trajectory based on which orbit was clicked
  let trajectoryPath = "";
  if (deorbitData) {
    const { x: startX, y: startY, orbit } = deorbitData;
    const centerX = 380;
    const centerY = 350;
    const dx = startX - centerX;
    const dy = startY - centerY;

    if (orbit === 3) {
      // Direct descent
      trajectoryPath = `M ${startX} ${startY} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 2) {
      // 1 transfer orbit -> Orbit 3 -> Surface
      const midX = centerX - dx * 0.7;
      const midY = centerY - dy * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 170 130 -10 0 1 ${midX} ${midY} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 1) {
      // 2 transfer orbits -> Orbit 2 -> Orbit 3 -> Surface
      const mid1X = centerX - dx * 0.74;
      const mid1Y = centerY - dy * 0.74;
      const dx2 = mid1X - centerX;
      const dy2 = mid1Y - centerY;
      const mid2X = centerX - dx2 * 0.7;
      const mid2Y = centerY - dy2 * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 230 160 -15 0 1 ${mid1X} ${mid1Y} A 170 130 -10 0 1 ${mid2X} ${mid2Y} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    }
  }
"""

content = content.replace("const stars = useMemo(() => Array.from", dynamic_path_logic.strip() + "\n\n  const stars = useMemo(() => Array.from")

# 3. Update the click handlers on the orbits to pass the index
# We know the specific coordinates used for the transparent hitboxes
hitbox_1 = r'<ellipse cx="280" cy="350" rx="270" ry="180" transform="rotate\(-15 280 350\)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick=\{handleOrbitClick\} />'
hitbox_2 = r'<ellipse cx="340" cy="350" rx="200" ry="150" transform="rotate\(-10 340 350\)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick=\{handleOrbitClick\} />'
hitbox_3 = r'<ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate\(-5 400 350\)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick=\{handleOrbitClick\} />'

content = re.sub(hitbox_1, hitbox_1.replace('onClick={handleOrbitClick}', 'onClick={(e) => handleOrbitClick(e, 1)}'), content)
content = re.sub(hitbox_2, hitbox_2.replace('onClick={handleOrbitClick}', 'onClick={(e) => handleOrbitClick(e, 2)}'), content)
content = re.sub(hitbox_3, hitbox_3.replace('onClick={handleOrbitClick}', 'onClick={(e) => handleOrbitClick(e, 3)}'), content)


# 4. Update the path rendering block to use deorbitData and trajectoryPath
old_render_block = r"\{deorbitPoint && \([\s\S]+?strokeDasharray=\"4 4\"\s*\/>\s*<\/g>\s*\)\}"

new_render_block = """{deorbitData && (
              <g>
                {/* Deorbit Burn Point */}
                <g transform={`translate(${deorbitData.x}, ${deorbitData.y})`}>
                  <circle cx="0" cy="0" r="4" fill="#10b981" />
                  <circle cx="0" cy="0" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
                  <text x="-45" y="-10" fill="#10b981" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>
                </g>
                {/* Final Descent Trajectory (dynamic multi-stage spiral) */}
                <path 
                  d={trajectoryPath} 
                  fill="none" 
                  stroke="#10b981" 
                  strokeWidth="3" 
                  strokeDasharray="4 4"
                />
              </g>
            )}"""

content = re.sub(old_render_block, new_render_block, content)

# 5. Update the execute button states
content = content.replace("deorbitPoint", "deorbitData")

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated spiral logic successfully!")
