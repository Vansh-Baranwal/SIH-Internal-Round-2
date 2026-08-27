import re

with open('web/src/components/OrbitalPlanner.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the onClick assignments for the 3 transparent ellipses
# We find them by their unique rx/ry radii
c1 = content.replace(
    'rx="270" ry="180" transform="rotate(-15 280 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={handleOrbitClick}',
    'rx="270" ry="180" transform="rotate(-15 280 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={(e) => handleOrbitClick(e, 1)}'
)
c2 = c1.replace(
    'rx="200" ry="150" transform="rotate(-10 340 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={handleOrbitClick}',
    'rx="200" ry="150" transform="rotate(-10 340 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={(e) => handleOrbitClick(e, 2)}'
)
c3 = c2.replace(
    'rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={handleOrbitClick}',
    'rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="transparent" strokeWidth="20" className="cursor-crosshair hover:stroke-white/10 transition-colors" onClick={(e) => handleOrbitClick(e, 3)}'
)

with open('web/src/components/OrbitalPlanner.tsx', 'w', encoding='utf-8') as f:
    f.write(c3)
print("Added orbit indices to onClick!")
