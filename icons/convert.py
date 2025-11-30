import os
import sys
import subprocess

SVG_PATH = sys.argv[1] if len(sys.argv) > 1 else '.'

def svg2png(input_folder, output_folder, size=32, padding=0):
  if not os.path.exists(output_folder):
    os.makedirs(output_folder)
  for filename in os.listdir(input_folder):
    if filename.lower().endswith('.svg'):
      input_path = os.path.join(input_folder, filename)
      output_name = os.path.splitext(filename)[0] + '.png'
      output_path = os.path.join(output_folder, output_name)
      temp_path = output_path if padding <= 0 \
        else os.path.join(output_folder, 'temp.png')
      # Convert SVG to PNG using Inkscape
      subprocess.run([
        'inkscape',
        input_path,
        '--export-width', str(size),
        '--export-height', str(size),
        '--export-type', 'png',
        '--export-filename', temp_path
      ])
      if padding > 0:
        # Add transparent border using ImageMagick
        subprocess.run([
          'magick',
          temp_path,
          '-bordercolor', 'none',
          '-border', str(padding),
          output_path
        ])
        os.remove(temp_path)
      print(f"Converted: {filename} --> {output_name}")

svg2png(SVG_PATH, SVG_PATH, size=48)
