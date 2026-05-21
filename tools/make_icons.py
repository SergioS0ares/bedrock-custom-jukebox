from PIL import Image
import os

src_dir = r'frontend/juke-crafter/src/assets/kenney'
out_dir = r'frontend/juke-crafter/src/assets/icons'
os.makedirs(out_dir, exist_ok=True)

mapping = {
    'disc': 'preview.png',
    'folder': 'sample.png',
    'youtube': 'preview.png',
    'check': 'sample.png'
}

for name, src in mapping.items():
    src_path = os.path.join(src_dir, src)
    if not os.path.exists(src_path):
        print('MISSING', src_path)
        continue
    im = Image.open(src_path).convert('RGBA')
    im = im.resize((48,48), Image.NEAREST)
    out_path = os.path.join(out_dir, f'{name}.png')
    im.save(out_path)
    print('SAVED', out_path)
