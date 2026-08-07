"""
MyNet Protocol - Lightweight secure protocol and browser for mynet:// URLs
"""

from setuptools import setup, find_packages
import os

# Read README for long description
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="mynet-protocol",
    version="1.0.0",
    description="Lightweight secure protocol and browser for mynet:// URLs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="MyNet Project",
    author_email="mynet@example.com",
    license="MIT",
    keywords="mynet protocol tls ssl http replacement lightweight security",
    python_requires=">=3.9",
    install_requires=[
        # No external dependencies!
    ],
    extras_require={
         "browser": [
            "PyQt6",
        ],
        "packaging": [
            "pyinstaller",
        ],
    },
    entry_points={
        "console_scripts": [
            "mynet=mynet:main_cli",
        ],
         "gui_scripts": [
            "mynet-browser=browser:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Security :: Cryptography",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Bug Reports": "https://github.com/gluedarwin/mynet/issues",
        "Source": "https://github.com/gluedarwin/mynet",
    },
)
