from setuptools import setup, find_packages

setup(
    name="multi-agent-dev-system",
    version="1.0.0",
    author="Pranav Apsingekar",
    author_email="pranavapsingekar@gmail.com",
    description="Autonomous 5-Agent Software Development System API backend powering VS Code Extension.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Pranav5317/ai-kimi-coding-system",
    packages=find_packages(),
    py_modules=["server", "main"],
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "multi-agent-server=server:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)

