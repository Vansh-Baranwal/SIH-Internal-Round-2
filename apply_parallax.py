with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_imports = "import { motion } from 'framer-motion';"
new_imports = "import { motion, useScroll, useTransform } from 'framer-motion';"
content = content.replace(old_imports, new_imports)

old_imports2 = "import { useEffect } from 'react';"
new_imports2 = "import { useEffect, useRef } from 'react';"
content = content.replace(old_imports2, new_imports2)

# 2. Add parallax hooks after the hash/useLocation block
old_hook = "const { hash } = useLocation();"
new_hook = """const { hash } = useLocation();
  const heroRef = useRef<HTMLElement>(null);
  const pipelineRef = useRef<HTMLDivElement>(null);

  // Parallax: Hero section
  const { scrollYProgress: heroScroll } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"]
  });
  const moonY = useTransform(heroScroll, [0, 1], ["0%", "30%"]);
  const heroTextY = useTransform(heroScroll, [0, 1], ["0%", "50%"]);
  const glowX = useTransform(heroScroll, [0, 1], ["0%", "-20%"]);

  // Parallax: Pipeline section
  const { scrollYProgress: pipelineScroll } = useScroll({
    target: pipelineRef,
    offset: ["start end", "end start"]
  });
  const pipelineTitleY = useTransform(pipelineScroll, [0, 1], ["40px", "-40px"]);
  const pipelineGlow1Y = useTransform(pipelineScroll, [0, 1], ["0%", "-30%"]);
  const pipelineGlow2Y = useTransform(pipelineScroll, [0, 1], ["0%", "20%"]);"""

content = content.replace(old_hook, new_hook)

# 3. Hero section: add ref
old_hero_section = '<section className="relative min-h-[85vh] flex flex-col justify-center pt-32 pb-16 px-8 lg:px-24 overflow-hidden border-b border-white/5 bg-[#0a0a0a]">'
new_hero_section = '<section ref={heroRef} className="relative min-h-[85vh] flex flex-col justify-center pt-32 pb-16 px-8 lg:px-24 overflow-hidden border-b border-white/5 bg-[#0a0a0a]">'
content = content.replace(old_hero_section, new_hero_section)

# 4. Moon image: wrap in motion.img with parallax
old_moon = """<img 
          src="/src/assets/moon.webp" 
          className="absolute bottom-0 right-0 w-[1000px] lg:w-[1300px] 2xl:w-[1600px] max-w-none object-contain translate-x-[50%] translate-y-[50%] opacity-40 mix-blend-screen pointer-events-none z-0" 
          style={{ WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)', maskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)' }}
        />"""
new_moon = """<motion.img 
          src="/src/assets/moon.webp" 
          style={{ y: moonY, WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)', maskImage: 'linear-gradient(to bottom, transparent 0%, black 15%)' }}
          className="absolute bottom-0 right-0 w-[1000px] lg:w-[1300px] 2xl:w-[1600px] max-w-none object-contain translate-x-[50%] translate-y-[50%] opacity-40 mix-blend-screen pointer-events-none z-0" 
        />"""
content = content.replace(old_moon, new_moon)

# 5. Hero text wrapper: add parallax y
old_text_wrapper = """<motion.div 
          variants={sentenceVariant}
          initial="hidden" 
          animate="visible" 
          className="relative z-20 max-w-4xl mt-16"
        >"""
new_text_wrapper = """<motion.div 
          variants={sentenceVariant}
          initial="hidden" 
          animate="visible" 
          style={{ y: heroTextY }}
          className="relative z-20 max-w-4xl mt-16"
        >"""
content = content.replace(old_text_wrapper, new_text_wrapper)

# 6. Mission section glow: parallax
old_glow1 = '<div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-white/5 rounded-full blur-[150px] pointer-events-none mix-blend-screen" />'
new_glow1 = '<motion.div style={{ x: glowX }} className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-white/5 rounded-full blur-[150px] pointer-events-none mix-blend-screen" />'
content = content.replace(old_glow1, new_glow1, 1)

# 7. Pipeline section: add ref and parallax glows
old_pipeline_div = '<div className="relative mt-32 w-full max-w-[1400px] mx-auto">'
new_pipeline_div = '<div ref={pipelineRef} className="relative mt-32 w-full max-w-[1400px] mx-auto">'
content = content.replace(old_pipeline_div, new_pipeline_div)

# Pipeline ambient glows with parallax
old_pglow1 = '<div className="absolute top-1/4 left-1/4 w-96 h-96 bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
new_pglow1 = '<motion.div style={{ y: pipelineGlow1Y }} className="absolute top-1/4 left-1/4 w-96 h-96 bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
content = content.replace(old_pglow1, new_pglow1)

old_pglow2 = '<div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
new_pglow2 = '<motion.div style={{ y: pipelineGlow2Y }} className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-white/5 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />'
content = content.replace(old_pglow2, new_pglow2)

# 8. Pipeline title: parallax
old_pipeline_title = """<div className="lg:col-span-5 flex flex-col items-center lg:items-start text-center lg:text-left h-full justify-center">
                <p className="text-zinc-500 font-bold tracking-widest text-[10px] uppercase mb-6">Methodology</p>
                <h3 className="text-6xl lg:text-[5rem] font-semibold text-white tracking-tighter mb-8 leading-[1.05]">
                  Our<br/>Pipeline
                </h3>
                <p className="text-zinc-500 text-xs font-medium tracking-wide">Scope: 6 Phases | Execution: Automated</p>
              </div>"""
new_pipeline_title = """<motion.div style={{ y: pipelineTitleY }} className="lg:col-span-5 flex flex-col items-center lg:items-start text-center lg:text-left h-full justify-center">
                <p className="text-zinc-500 font-bold tracking-widest text-[10px] uppercase mb-6">Methodology</p>
                <h3 className="text-6xl lg:text-[5rem] font-semibold text-white tracking-tighter mb-8 leading-[1.05]">
                  Our<br/>Pipeline
                </h3>
                <p className="text-zinc-500 text-xs font-medium tracking-wide">Scope: 6 Phases | Execution: Automated</p>
              </motion.div>"""
content = content.replace(old_pipeline_title, new_pipeline_title)

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Parallax scrolling applied!")
