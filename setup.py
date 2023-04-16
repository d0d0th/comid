from setuptools import setup

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setup(
    name='comid',
    version='0.0.2',
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
                      'pmaw'
                      ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3 :: Only",
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9'
)
