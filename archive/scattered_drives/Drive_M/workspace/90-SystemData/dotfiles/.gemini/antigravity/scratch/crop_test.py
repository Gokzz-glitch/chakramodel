from PIL import Image

im = Image.open(r"C:\Users\imgk3\.gemini\antigravity\scratch\page_1.png")
print("Image size:", im.size)
print("Image mode:", im.mode)

# Let's inspect vertical slice or crop out the chat content
# In 2102x4000:
# Top header is around y=200 to 400
# User bubble "i wanna know about colonoscopy" is around y=300 to 500, x=1200 to 1800
# Assistant text starts around y=600 down to y=3000
# Bottom input area is y=3100 to 3400
# Windows taskbar is y=3400 to 3600
# Motorola banner is y=3600 to 4000
