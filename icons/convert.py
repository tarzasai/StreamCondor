import os
import subprocess

def convert_with_padding(input_folder, output_folder, size=32, padding=2):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    for filename in os.listdir(input_folder):
        if filename.lower().endswith('.svg'):
            input_path = os.path.join(input_folder, filename)
            output_filename = os.path.splitext(filename)[0] + '.png'
            output_path = os.path.join(output_folder, output_filename)
            
            # First convert with Inkscape
            temp_path = os.path.join(output_folder, 'temp.png')
            cmd_inkscape = [
                'inkscape',
                input_path,
                '--export-width', str(size),
                '--export-height', str(size),
                '--export-type', 'png',
                '--export-filename', temp_path
            ]
            subprocess.run(cmd_inkscape)
            
            # Then add padding with ImageMagick
            cmd_magick = [
                'magick',
                temp_path,
                '-bordercolor', 'none',
                '-border', str(padding),
                output_path
            ]
            subprocess.run(cmd_magick)
            
            # Clean up temp file
            os.remove(temp_path)
            print(f"Converted: {filename}")

convert_with_padding('.', 'output_pngs/', size=28, padding=2)