import re
from pathlib import Path

from setuptools import setup

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

# The version lives only in comid/__init__.py; it is read without importing the package, whose
# dependencies may not be installed yet when this script runs.
_init_source = (Path(__file__).resolve().parent / "comid" / "__init__.py").read_text(encoding="utf-8")
_version_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', _init_source, re.MULTILINE)
if _version_match is None:
    raise RuntimeError("Could not find __version__ in comid/__init__.py")

setup(
    name='comid',
    version=_version_match.group(1),
    packages=['comid'],
    url='https://github.com/d0d0th/comid',
    license='MIT License',
    author='Thiago Henrique dos Santos',
    author_email='a22100011@alunos.ulht.pt',
    description='A community identification module for Reddit conversations',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    install_requires=['redditcleaner',
                      'contractions',
                      'nltk',
                      'spacy',
                      'tqdm',
                      'pandas',
                      'praw>=7.7',
                      'requests',
                      'numpy',
                      'convokit>=3.1.0'
                      ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3 :: Only",
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
    options={"bdist_wheel": {"python_tag": "py3"}},
)
