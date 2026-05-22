from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class MasterResume(Base):
    __tablename__ = "master_resumes"

    id = Column(Integer, primary_key=True, index=True)
    # Since we are single-tenant, we might not strictly need user_id, 
    # but good for future-proofing or simple session tracking
    email = Column(String, index=True, nullable=True) 
    
    # Store the parsed resume data to avoid re-parsing
    parsed_data = Column(JSON, nullable=False)
    original_text = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    applications = relationship("JobApplication", back_populates="master_resume")

class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    master_resume_id = Column(Integer, ForeignKey("master_resumes.id"))
    
    company_name = Column(String, index=True)
    role_title = Column(String, index=True)
    job_description = Column(Text, nullable=False)
    
    match_score = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    master_resume = relationship("MasterResume", back_populates="applications")
    generations = relationship("Generation", back_populates="application")

class Generation(Base):
    __tablename__ = "generations"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("job_applications.id"))
    
    # "resume", "cover_letter", "interview_prep"
    generation_type = Column(String, index=True) 
    
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    application = relationship("JobApplication", back_populates="generations")
