from crewai import Agent, Task, Crew, Process
from crewai_tools import CodeInterpreterTool
import os

# Set the Docker socket path for macOS
os.environ['DOCKER_HOST'] = f'unix://{os.path.expanduser("~/.docker/run/docker.sock")}'

# Initialize the code interpreter tool
code_interpreter = CodeInterpreterTool()

# Create an agent that can write and execute code
programmer = Agent(
    role="Python Programmer",
    goal="Write and execute Python code to solve problems",
    backstory="An expert Python programmer who writes efficient code.",
    tools=[code_interpreter],
    verbose=True
)

# Create a simple task for the agent
task = Task(
    description="Write a Python function to calculate the Fibonacci sequence up to the 10th number and print the result.",
    expected_output="A list containing the first 10 numbers of the Fibonacci sequence",
    agent=programmer
)

# Create and run the crew
crew = Crew(
    agents=[programmer],
    tasks=[task],
    process=Process.sequential
)

# Execute the task
result = crew.kickoff()
print(f"Result: {result}")