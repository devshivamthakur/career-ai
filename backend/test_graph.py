import asyncio
from app.agents.resume_tailor import ResumeTailorAgent

async def main():
    agent = ResumeTailorAgent()
    async for chunk in agent.astream_tailored_resume("I am a python developer", "We need a python developer with django"):
        print("CHUNK:", chunk)

asyncio.run(main())
