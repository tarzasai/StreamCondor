#!/usr/bin/env python3
"""
Setup script for StreamCondor.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

# Read requirements
requirements_file = Path(__file__).parent / 'requirements.txt'
requirements = []
if requirements_file.exists():
  requirements = requirements_file.read_text(encoding='utf-8').strip().split('\n')

setup(
  name='streamcondor',
  version='1.0.0',
  description='A system tray application for monitoring livestreams',
  long_description=long_description,
  long_description_content_type='text/markdown',
  author='StreamCondor Contributors',
  url='https://github.com/yourusername/streamcondor',
  packages=find_packages(),
  install_requires=requirements,
  python_requires='>=3.12',
  entry_points={
    'console_scripts': [
      'streamcondor=src.main:main',
    ],
  },
  classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: End Users/Desktop',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.12',
    'Operating System :: OS Independent',
  ],
  include_package_data=True,
  package_data={
    'src': ['assets/*.png', 'assets/*.svg'],
  },
)
