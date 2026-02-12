from setuptools import setup
setup(name="agent-log-analyzer",version="0.1.0",
    description="Parse and analyze AI agent session logs",
    long_description=open("README.md").read(),long_description_content_type="text/markdown",
    author="Lei Hua",url="https://github.com/leiMizzou/agent-log-analyzer",
    py_modules=["agent_log"],python_requires=">=3.8",
    entry_points={"console_scripts":["agent-log-analyzer=agent_log:main"]})
