from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.pipelines.ingestion_pipeline import IngestionPipeline


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

pipeline = IngestionPipeline()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    document_id = str(uuid4())

    pdf_path = (
        settings.uploads_dir
        / f"{document_id}.pdf"
    )

    try:

        with pdf_path.open("wb") as buffer:

            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)

        result = pipeline.run(
            pdf_path=pdf_path,
            document_id=document_id,
        )

        return {
            "status": "ready",
            "filename": file.filename,
            **result,
        }

    except Exception as exc:

        if pdf_path.exists():
            pdf_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()