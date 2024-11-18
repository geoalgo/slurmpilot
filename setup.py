from setuptools import setup, find_packages

setup(
    name="slurmpilot",
    version="0.0.0",
    packages=find_packages(),
    install_requires=[
        "pyyaml",
        "pandas",
        "fabric",
    ],
    extras_require={
        "dev": ["pytest", "black", "pre-commit"],
        "extra": ["coolname", "rich"],
    },
    entry_points={
        "console_scripts": [
            "slurmpilot=slurmpilot.cli.cli:main",
            "sp=slurmpilot.cli.cli:main",
            "sp-add-cluster=slurmpilot.cli.add_cluster:main",
            "sp-usage=slurmpilot.cli.usage:main",
        ],
    },
)
