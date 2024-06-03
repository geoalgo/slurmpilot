from setuptools import setup, find_packages

setup(
    name="slurmpilot",
    version="0.0.0",
    packages=find_packages(),
    install_requires=[
        "pyyaml",
        "fabric",
    ],
    extras_require={
        "dev": ["pytest", "black", "pre-commit"],
        "extra": ["coolname"],
    },
    entry_points={
        "console_scripts": [
            "slurmpilot=slurmpilot.cli:main",
        ],
    },
)
