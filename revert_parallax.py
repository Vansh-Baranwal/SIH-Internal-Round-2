with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Revert imports
content = content.replace("import { motion, useScroll, useTransform } from 'framer-motion';", "import { motion } from 'framer-motion';")
content = content.replace("import { useEffect, useRef } from 'react';", "import { useEffect } from 'react';")

# 2. Remove all the parallax hooks (heroRef, pipelineRef, useScroll, useTransform)
import re
content = re.sub(
    r'  const heroRef = useRef.*?const pipelineGlow2Y = useTransform\(pipelineScroll, \[0, 1\], \["0%", "20%"\]\);',
    '',
    content,
    flags=re.DOTALL
)

# 3. Revert hero section ref
content = content.replace('ref={heroRef} className="relative min-h-[85vh]', 'className="relative min-h-[85vh]')

# 4. Revert motion.img back to img
content = content.replace('<motion.img', '<img')
content = content.replace(
    """style={{ y: moonY, WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)', maskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)' }}
          className="absolute bottom-0 right-0""",
    """className="absolute bottom-0 right-0"""
)
# Add back the style prop inline
content = content.replace(
    'mix-blend-screen pointer-events-none z-0" \n        />',
    """mix-blend-screen pointer-events-none z-0" \n          style={{ WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)', maskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)' }}\n        />"""
)

# 5. Revert hero text wrapper
content = content.replace(
    """variants={sentenceVariant}
          initial="hidden" 
          animate="visible" 
          style={{ y: heroTextY }}""",
    """variants={sentenceVariant}
          initial="hidden" 
          animate="visible\""""
)

# 6. Revert mission glow
content = content.replace(
    '<motion.div style={{ x: glowX }} className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-white/5 rounded-full blur-[150px] pointer-events-none mix-blend-screen" />',
    '<div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-white/5 rounded-full blur-[150px] pointer-events-none mix-blend-screen" />'
)

# 7. Revert pipeline ref
content = content.replace('ref={pipelineRef} className="relative mt-32', 'className="relative mt-32')

# 8. Revert pipeline glows
content = content.replace(
    '<motion.div style={{ y: pipelineGlow1Y }} className="absolute top-1/4 left-1/4 w-96 h-96 bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />',
    '<div className="absolute top-1/4 left-1/4 w-96 h-96 bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
)
content = content.replace(
    '<motion.div style={{ y: pipelineGlow2Y }} className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />',
    '<div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
)

# 9. Revert pipeline title
content = content.replace(
    '<motion.div style={{ y: pipelineTitleY }} className="lg:col-span-5',
    '<div className="lg:col-span-5'
)
content = content.replace(
    """<p className="text-zinc-500 text-xs font-medium tracking-wide">Scope: 6 Phases | Execution: Automated</p>
              </motion.div>""",
    """<p className="text-zinc-500 text-xs font-medium tracking-wide">Scope: 6 Phases | Execution: Automated</p>
              </div>"""
)

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Parallax reverted!")
