import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='latin-1') as f:
    content = f.read()

new_path = """
            {/* Deorbit Burn Point on Orbit 3 */}
            <g transform="translate(274, 298)">
              <circle cx="0" cy="0" r="4" fill="#10b981" />
              <circle cx="0" cy="0" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
              <text x="-40" y="-10" fill="#10b981" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>
            </g>

            {/* Final Descent Trajectory (dynamic elliptical arc mimicking the orbit) */}
            <path 
              d={`M 274 298 A 120 100 -5 0 1 ${visualTargetX} ${visualTargetY}`} 
              fill="none" 
              stroke="#10b981" 
              strokeWidth="3" 
              strokeDasharray="4 4"
            />"""

# Regex replace
content = re.sub(
    r"\{\/\* Final Descent Trajectory \(dynamic\)[^\}]+\}\s*<path\s*d=\{\`M [^\`]+\`\}\s*fill=\"none\"\s*stroke=\"#10b981\"\s*strokeWidth=\"3\"\s*strokeDasharray=\"4 4\"\s*\/>",
    new_path.strip(),
    content
)

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated descent trajectory path!")
