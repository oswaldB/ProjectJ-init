
from fastapi import FastAPI
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
import asyncio
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI()

class CrewRequest(BaseModel):
    task_description: str
    agents: List[str]

@app.get("/")
async def root():
    return {"message": "CrewAI FastAPI Server"}

@app.post("/execute-crew")
async def execute_crew(request: CrewRequest):
    # Create agents
    researcher = Agent(
        role='Researcher',
        goal='Research and gather information',
        backstory='Expert at gathering and analyzing information',
        allow_delegation=False
    )
    
    writer = Agent(
        role='Writer',
        goal='Write clear and concise content',
        backstory='Expert content writer and editor',
        allow_delegation=False
    )

    # Create task
    task = Task(
        description=request.task_description,
        agent=researcher
    )

    # Create crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[task]
    )

    # Execute crew task
    result = await asyncio.to_thread(crew.kickoff)
    
    return {"result": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
