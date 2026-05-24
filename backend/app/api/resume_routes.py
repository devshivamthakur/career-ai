"""
Resume Tailor API Endpoints
FastAPI routes for resume tailoring, streaming, and export.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import os
from typing import Generator
import logging
import json

from app.agents.resume_tailor import ResumeTailorAgent
from app.services.pdf_service import PDFParsingService
from app.services.pdf_export import PDFExportService
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])

# Initialize the Resume Tailor Agent
try:
    resume_tailor_agent = ResumeTailorAgent(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Resume Tailor Agent: {str(e)}")
    resume_tailor_agent = None


@router.post("/upload")
async def upload_master_resume(file: UploadFile = File(...)):
    """
    Upload a master resume PDF file.
    Extracts and stores the resume text and structured data.
    
    Args:
        file: PDF file to upload
        
    Returns:
        Extracted resume data and metadata
    """
    try:
        # Validate file type
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Validate PDF
            if not PDFParsingService.validate_pdf_file(tmp_path):
                raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file")
            
            # Extract text
            extracted_text = PDFParsingService.extract_text_from_pdf(tmp_path)
            
            if not extracted_text:
                raise HTTPException(status_code=400, detail="No text found in PDF")
            
            # Parse structured data
            structured_data = PDFParsingService.extract_structured_data(extracted_text)
            
            return {
                "status": "success",
                "message": "Resume uploaded and parsed successfully",
                "data": {
                    "text_length": len(extracted_text),
                    "contact_info": structured_data.get("contact_info", {}),
                    "skills_count": len(structured_data.get("skills", [])),
                    "experience_count": len(structured_data.get("experience", [])),
                    "education_count": len(structured_data.get("education", [])),
                    "parsed_data": structured_data,
                }
            }
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/tailor/stream")
async def tailor_resume_stream(
    master_resume: str = Form(...),
    job_description: str = Form(...)
):
    """
    Tailor a resume to a job description with streaming response.
    Streams the tailored resume content as it's generated.
    
    Args:
        master_resume: The user's master resume text
        job_description: The job posting to tailor for
        
    Returns:
        Streaming response with tailored resume content
    """
    if not resume_tailor_agent:
        raise HTTPException(
            status_code=500,
            detail="Resume tailor service is not available. Check ANTHROPIC_API_KEY."
        )
    
    try:
        def generate() -> Generator[str, None, None]:
            """Generator that streams the tailored resume."""
            try:
                # Run the tailoring workflow
                tailored_resume = resume_tailor_agent.tailor_resume(
                    master_resume=master_resume,
                    job_description=job_description
                )
                
                # Stream the response in chunks
                chunk_size = 100
                for i in range(0, len(tailored_resume), chunk_size):
                    chunk = tailored_resume[i:i + chunk_size]
                    # Send as Server-Sent Events format
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in stream generation: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    
    except Exception as e:
        logger.error(f"Error in tailor_resume_stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error tailoring resume: {str(e)}")


@router.post("/export-pdf")
async def export_tailored_resume(
    resume_text: str = Form(...)
):
    """
    Export tailored resume as a PDF file.
    
    Args:
        resume_text: The tailored resume text
        
    Returns:
        PDF file download
    """
    try:
        # Generate PDF
        pdf_buffer = PDFExportService.generate_pdf(resume_text)
        
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=tailored_resume.pdf"}
        )
    
    except Exception as e:
        logger.error(f"Error exporting PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.get("/status")
async def resume_service_status():
    """
    Check the status of the resume tailor service.
    
    Returns:
        Service status and configuration info
    """
    return {
        "status": "operational" if resume_tailor_agent else "unavailable",
        "service": "Resume Tailor",
        "version": "1.0.0",
        "features": [
            "PDF upload and parsing",
            "Resume tailoring with streaming",
            "PDF export",
        ]
    }
