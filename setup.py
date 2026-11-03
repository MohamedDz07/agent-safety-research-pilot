"""Compatibility with older pip installations that cannot edit-install PEP 621 projects."""
from setuptools import find_packages, setup

setup(
    name="agent-safety-research-pilot",
    version="0.1.0",
    description="A synthetic bilingual benchmark for tool authorization under prompt injection",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={"agent_safety": ["data/cases.json"]},
    python_requires=">=3.9",
    extras_require={"anthropic": ["anthropic>=0.40"]},
    entry_points={"console_scripts": ["agent-safety=agent_safety.cli:main"]},
)
