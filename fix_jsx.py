import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """              </button>
            </div>
          </motion.div>"""
new_block = """              </button>
            </motion.div>
          </motion.div>"""

content = content.replace(old_block, new_block)

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed JSX closing tag!")
