"""
Resume Tailor LangGraph Agent
Orchestrates the resume tailoring workflow using LangGraph and Claude via LangChain.
"""

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


# Define the state schema for the graph
class ResumeTailorState(BaseModel):
    """State object for the resume tailoring workflow."""
    master_resume: str
    job_description: str
    jd_skills: List[str] = []
    master_skills: List[str] = []
    skill_gaps: List[str] = []
    tailored_sections: Dict[str, str] = {}
    final_resume: str = ""
    error: str = None


class ResumeTailorAgent:
    """
    LangGraph-based agent for tailoring resumes to job descriptions.
    """

    def __init__(self, api_key: str):
        """
        Initialize the Resume Tailor Agent.
        
        Args:
            api_key: OpenAI API key
        """
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4",  # Use gpt-4 for better quality
            temperature=0.7,
            max_tokens=2000,
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ResumeTailorState)

        # Add nodes
        workflow.add_node("parse_jd", self._parse_job_description)
        workflow.add_node("extract_skills", self._extract_skills)
        workflow.add_node("compare_skills", self._compare_skills)
        workflow.add_node("rewrite_resume", self._rewrite_resume)
        workflow.add_node("finalize", self._finalize_resume)

        # Add edges
        workflow.add_edge("parse_jd", "extract_skills")
        workflow.add_edge("extract_skills", "compare_skills")
        workflow.add_edge("compare_skills", "rewrite_resume")
        workflow.add_edge("rewrite_resume", "finalize")
        workflow.add_edge("finalize", END)

        # Set entry point
        workflow.set_entry_point("parse_jd")

        return workflow.compile()

    def _parse_job_description(self, state: ResumeTailorState) -> Dict[str, Any]:
        """
        Parse the job description to extract key information.
        """
        logger.info("Parsing job description...")
        
        prompt = f"""
        Analyze the following job description and extract key requirements, 
        responsibilities, and qualifications. Focus on technical skills, 
        soft skills, and experience required.
        
        Job Description:
        {state.job_description}
        
        Provide a structured analysis with:
        1. Key technical skills required
        2. Key soft skills required
        3. Years of experience needed
        4. Key responsibilities
        """

        response = self.llm.invoke(prompt)
        
        # Extract structured data from response
        state.jd_skills = self._extract_skills_from_text(response.content)
        
        return {
            "jd_skills": state.jd_skills,
        }

    def _extract_skills(self, state: ResumeTailorState) -> Dict[str, Any]:
        """
        Extract skills from the master resume.
        """
        logger.info("Extracting skills from master resume...")
        
        prompt = f"""
        Extract all technical skills, soft skills, and tools from this resume.
        Return as a comma-separated list.
        
        Resume:
        {state.master_resume}
        """

        response = self.llm.invoke(prompt)
        skills_text = response.content
        master_skills = [s.strip() for s in skills_text.split(",")]
        
        return {
            "master_skills": master_skills,
        }

    def _compare_skills(self, state: ResumeTailorState) -> Dict[str, Any]:
        """
        Compare job description skills with master resume skills.
        Identify gaps and matching skills.
        """
        logger.info("Comparing skills...")
        
        prompt = f"""
        Compare the following two skill lists:
        
        Job Description Skills: {', '.join(state.jd_skills)}
        Master Resume Skills: {', '.join(state.master_skills)}
        
        Identify:
        1. Skills present in JD but missing from resume (skill gaps)
        2. Skills present in both (matching skills)
        3. Recommendations for bridging gaps
        
        Return the skill gaps as a comma-separated list.
        """

        response = self.llm.invoke(prompt)
        gaps_text = response.content
        skill_gaps = [g.strip() for g in gaps_text.split(",") if g.strip()]
        
        return {
            "skill_gaps": skill_gaps,
        }

    def _rewrite_resume(self, state: ResumeTailorState) -> Dict[str, Any]:
        """
        Rewrite specific resume sections to better match the job description.
        """
        logger.info("Rewriting resume sections...")
        
        prompt = f"""
        Given the following master resume and job description, 
        rewrite the resume to better match the job requirements.
        Focus on:
        1. Highlighting relevant experience for this specific role
        2. Emphasizing skills that match the JD
        3. Reordering bullet points to prioritize relevant achievements
        4. Using keywords from the JD naturally
        
        Master Resume:
        {state.master_resume}
        
        Job Description:
        {state.job_description}
        
        Skill Gaps Identified: {', '.join(state.skill_gaps)}
        
        Provide a tailored version of the resume that maintains the original structure
        but highlights the most relevant experience for this job.
        """

        response = self.llm.invoke(prompt)
        tailored_resume = response.content
        
        return {
            "final_resume": tailored_resume,
        }

    def _finalize_resume(self, state: ResumeTailorState) -> Dict[str, Any]:
        """
        Final polishing of the tailored resume.
        """
        logger.info("Finalizing resume...")
        
        # The tailored resume is already ready from the rewrite step
        return {
            "final_resume": state.final_resume,
        }

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """
        Simple helper to extract skills from LLM response.
        """
        import re
        
        # Look for common skill indicators
        skills = re.findall(r"(?:skill|technology|tool|framework|language)s?:?\s*([^\n]+)", text, re.IGNORECASE)
        all_skills = []
        for skill_line in skills:
            all_skills.extend([s.strip() for s in skill_line.split(",") if s.strip()])
        
        return all_skills[:20]  # Return top 20 skills

    async def tailor_resume(self, master_resume: str, job_description: str) -> str:
        """
        Run the full resume tailoring workflow.
        
        Args:
            master_resume: The user's master resume text
            job_description: The job posting to tailor for
            
        Returns:
            Tailored resume text
        """
        logger.info("Starting resume tailoring workflow...")
        
        initial_state = ResumeTailorState(
            master_resume=master_resume,
            job_description=job_description,
        )
        
        try:
            result = self.graph.invoke(initial_state)
            return result.get("final_resume", "")
        except Exception as e:
            logger.error(f"Error in resume tailoring workflow: {str(e)}")
            raise
