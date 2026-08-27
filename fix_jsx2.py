import re

with open('web/src/pages/Landing.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the specific tag!
# The button group ends with:
#               <span>Read Documentation</span>
#             </button>
#           </div>
#         </motion.div>

content = re.sub(
    r"<\/button>\s*<\/div>\s*<\/motion\.div>",
    "</button>\n            </motion.div>\n          </motion.div>",
    content
)

with open('web/src/pages/Landing.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex replaced!")
