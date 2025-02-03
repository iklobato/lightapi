from setuptools import setup, find_packages
from pathlib import Path

readme_path = Path(__file__).parent / 'README.md'
long_description = readme_path.read_text(encoding='utf-8')

setup(
    name='lightapi',
    version='0.1.0',
    description='Lightweight API framework with native core and optional extensions',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords=[
        'rest',
        'api',
        'lightweight',
        'minimal',
        'jwt',
        'sqlalchemy',
        'middleware',
    ],
    author='Henrique Lobato',
    author_email='iklobato1@gmail.com',
    url='https://github.com/iklobato/LightApi',
    packages=find_packages(),
    install_requires=['pyjwt>=2.0.0', 'sqlalchemy>=1.4.0'],
    extras_require={
        'test': ['pytest>=7.0.0'],
        'docs': [
            'mkdocs-material',
            'mkdocstrings[python]',
            'mkdocs-glightbox',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    python_requires='>=3.7',
    license='MIT',
    project_urls={
        'Documentation': 'https://iklobato.github.io/LightApi',
        'Source': 'https://github.com/iklobato/LightApi',
        'Tracker': 'https://github.com/iklobato/LightApi/issues',
    },
)
