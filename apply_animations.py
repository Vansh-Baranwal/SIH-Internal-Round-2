import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add variants inside Landing component
variants = """
  const sentenceVariant = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        delay: 2.2, // Wait for global loader to finish
        staggerChildren: 0.08,
      },
    },
  };

  const letterVariant = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: "easeOut",
      }
    },
  };

  const wordVariant = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.5,
        ease: "easeOut",
      }
    },
  };
"""

content = re.sub(r'const \{ hash \} = useLocation\(\);', 'const { hash } = useLocation();\n' + variants, content)

# Modify the Hero text wrapper
old_hero = """<motion.div 
          initial={{ opacity: 0, y: 30 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 1, ease: 'easeOut' }}
          className="relative z-20 max-w-4xl mt-16"
        >
          <h1 className="text-[5rem] lg:text-[10rem] font-black tracking-tighter mb-8 leading-[0.9] uppercase">
            <span className="block text-white">LUNA</span>
            <span className="block text-transparent [-webkit-text-stroke:2px_white] lg:[-webkit-text-stroke:4px_white]">DRISHTI</span>
          </h1>
          
          <p className="text-lg lg:text-xl text-zinc-400 leading-relaxed mb-12 max-w-2xl font-medium">
            A geospatial intelligence platform for converting Chandrayaan-2 lunar observations into high-fidelity terrain hazard maps, landing-site assessments, and interactive descent trajectory physics.
          </p>"""

new_hero = """<motion.div 
          variants={sentenceVariant}
          initial="hidden" 
          animate="visible" 
          className="relative z-20 max-w-4xl mt-16"
        >
          <h1 className="text-[5rem] lg:text-[10rem] font-black tracking-tighter mb-8 leading-[0.9] uppercase">
            <span className="block text-white overflow-hidden">
              {"LUNA".split("").map((char, index) => (
                <motion.span key={index} variants={letterVariant} className="inline-block">{char}</motion.span>
              ))}
            </span>
            <span className="block text-transparent [-webkit-text-stroke:2px_white] lg:[-webkit-text-stroke:4px_white] overflow-hidden">
              {"DRISHTI".split("").map((char, index) => (
                <motion.span key={index} variants={letterVariant} className="inline-block">{char}</motion.span>
              ))}
            </span>
          </h1>
          
          <motion.p className="text-lg lg:text-xl text-zinc-400 leading-relaxed mb-12 max-w-2xl font-medium overflow-hidden">
            {"A geospatial intelligence platform for converting Chandrayaan-2 lunar observations into high-fidelity terrain hazard maps, landing-site assessments, and interactive descent trajectory physics.".split(" ").map((word, index) => (
              <motion.span key={index} variants={wordVariant} className="inline-block mr-1.5">{word}</motion.span>
            ))}
          </motion.p>"""

content = content.replace(old_hero, new_hero)

# Fix delay for the button group so it appears after the text
content = content.replace('<div className="flex space-x-6">', '<motion.div variants={wordVariant} className="flex space-x-6">')

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added letter-by-letter animations!")
