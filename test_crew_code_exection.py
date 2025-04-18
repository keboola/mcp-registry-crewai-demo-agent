#!/usr/bin/env python
import os
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import CodeInterpreterTool

@CrewBase
class CodeExecutionCrew:
    """
    A crew designed to write and execute Python code for solving problems.
    This example demonstrates using the CodeInterpreterTool to calculate
    the Fibonacci sequence.
    """
    
    def __init__(self, inputs=None):
        """
        Initializes the CodeExecutionCrew.
        Args:
            inputs (dict): Optional inputs for customizing tasks
        """
        # Set the Docker socket path for macOS
        os.environ["DOCKER_HOST"] = f'unix://{os.path.expanduser("~/.docker/run/docker.sock")}'
        
        # Store inputs
        self.inputs = inputs or {}
        
        # Initialize the code interpreter tool
        self.code_interpreter = CodeInterpreterTool()

    @agent
    def programmer_agent(self) -> Agent:
        """
        Creates a Python programmer agent with code execution capabilities.
        """
        return Agent(
            role="Python Programmer",
            goal="Write and execute Python code to solve problems",
            backstory="An expert Python programmer who writes efficient code.",
            tools=[self.code_interpreter],
            verbose=True,
        )

    @task
    def fibonacci_task(self) -> Task:
        """
        Creates a task for calculating the Fibonacci sequence.
        """
        # Get custom task description if provided in inputs, otherwise use default
        task_description = self.inputs.get("task_description", 
            "Write a Python function to calculate the Fibonacci sequence up to the 10th number and print the result.")
        
        return Task(
            description=task_description,
            expected_output="A list containing the first 10 numbers of the Fibonacci sequence",
            agent=self.programmer_agent(),
        )

    @crew
    def code_execution_crew(self) -> Crew:
        """
        Assembles the Code Execution Crew.
        """
        return Crew(
            agents=[self.programmer_agent()],
            tasks=[self.fibonacci_task()],
            process=Process.sequential,
            verbose=True
        )

# Example usage
if __name__ == "__main__":
    print("## Code Execution Crew Example")
    
    # Optional: customize the task via inputs
    custom_inputs = {
        # Uncomment to override the default task
        # "task_description": "Write a Python function to calculate the prime numbers up to 50 and print them."
    }
    
    # Instantiate the crew
    code_crew = CodeExecutionCrew(inputs=custom_inputs)
    
    # Kick off the crew process
    result = code_crew.code_execution_crew().kickoff()
    
    print("\n\n########################")
    print("## Crew Final Result:")
    print("########################")
    print(result)

