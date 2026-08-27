import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the dynamic trajectory generation to incorporate vx and vz into the transfer waypoints
old_logic = """
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

new_logic = """
  // Generate multi-stage spiral trajectory based on which orbit was clicked
  let trajectoryPath = "";
  if (deorbitData) {
    const { x: startX, y: startY, orbit } = deorbitData;
    
    // The injected velocity warps the orbital transfer centers! 
    // This makes the entire path morph from the departure point, rather than just shifting the final landing coordinate.
    const warpCenterX = 380 + (vx * 2);
    const warpCenterY = 350 + (vz * 2);
    
    const dx = startX - 380;
    const dy = startY - 350;

    if (orbit === 3) {
      // Direct descent: we manipulate the arc radii slightly based on velocity to warp the curve
      const rX = 130 + (vx * 1.5);
      const rY = 115 + (vz * 1.5);
      trajectoryPath = `M ${startX} ${startY} A ${Math.max(50, rX)} ${Math.max(50, rY)} -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 2) {
      // 1 transfer orbit -> Orbit 3 -> Surface
      const midX = warpCenterX - dx * 0.7;
      const midY = warpCenterY - dy * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 170 130 -10 0 1 ${midX} ${midY} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 1) {
      // 2 transfer orbits -> Orbit 2 -> Orbit 3 -> Surface
      const mid1X = warpCenterX - dx * 0.74;
      const mid1Y = warpCenterY - dy * 0.74;
      const dx2 = mid1X - warpCenterX;
      const dy2 = mid1Y - warpCenterY;
      const mid2X = warpCenterX - dx2 * 0.7;
      const mid2Y = warpCenterY - dy2 * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 230 160 -15 0 1 ${mid1X} ${mid1Y} A 170 130 -10 0 1 ${mid2X} ${mid2Y} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    }
  }
"""

content = content.replace(old_logic.strip(), new_logic.strip())

# 2. Add the Delta-V thrust vector arrow at the deorbit point
old_deorbit_marker = """<circle cx="0" cy="0" r="4" fill="#10b981" />
                  <circle cx="0" cy="0" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
                  <text x="-45" y="-10" fill="#10b981" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>"""

new_deorbit_marker = """<circle cx="0" cy="0" r="4" fill="#10b981" />
                  <circle cx="0" cy="0" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
                  {/* Delta-V Burn Vector Indicator */}
                  {(vx !== 0 || vz !== 0) && (
                    <g>
                      <line x1="0" y1="0" x2={vx * 2.5} y2={vz * 2.5} stroke="#ef4444" strokeWidth="2" />
                      <circle cx={vx * 2.5} cy={vz * 2.5} r="1.5" fill="#ef4444" />
                    </g>
                  )}
                  <text x="-45" y="-12" fill="#10b981" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>
                  {(vx !== 0 || vz !== 0) && <text x="-45" y="20" fill="#ef4444" fontSize="8" fontWeight="bold" opacity="0.8">?v BURN</text>}"""

content = content.replace(old_deorbit_marker, new_deorbit_marker)

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated orbital warp physics and delta-v vector!")
