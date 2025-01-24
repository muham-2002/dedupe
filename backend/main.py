from asyncio.log import logger
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from typing import Any, List
import tempfile
from dedupe_script import find_duplicates_in_files
import numpy as np
import json
from contextlib import asynccontextmanager

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup on shutdown
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

app = FastAPI(
    title="Deduplication API",
    description="API for finding duplicates in CSV and Excel files",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a temporary directory to store uploaded files
TEMP_DIR = tempfile.mkdtemp()

@app.post("/dedupe", response_class=JSONResponse)
async def dedupe_files(
    files: List[UploadFile] = File(...),
    similarity_threshold: float = Form(0.6),
    training_data: str = Form(None),
    selected_columns: str = Form(None)
):
    """
    Upload one or more CSV/Excel files and find duplicates.
    
    Args:
        files: List of files to process (CSV or Excel)
        similarity_threshold: Threshold for duplicate matching (0-1)
        training_data: Training data as JSON string
    """
    try:
        if selected_columns:
            print(f"Received selected columns: {selected_columns[:100]}...")  # Print first 100 chars for debugging
            logger.info(f"Received selected columns length: {len(selected_columns)}")
            selected_columns = json.loads(selected_columns)
        else:
            logger.info("No selected columns found")
        if training_data:
            print(f"Received training data: {training_data[:100]}...")  # Print first 100 chars for debugging
            logger.info(f"Received training data length: {len(training_data)}")
            training_data = json.loads(training_data)
        else:
            logger.info("No training data found")
        required_matches: int = 1
        max_training_matches: int = 5
        max_training_distincts: int = 5
        # Validate file types
        for file in files:
            if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for {file.filename}. Only CSV and Excel files are supported."
                )

        # Save uploaded files temporarily
        temp_files = []
        for file in files:
            temp_path = os.path.join(TEMP_DIR, file.filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            temp_files.append(temp_path)

        # Configure deduplication
        config = {
            'similarity_threshold': similarity_threshold,
            'required_matches': required_matches,
            'chunk_size': 50000,
            'max_training_matches': max_training_matches,
            'max_training_distincts': max_training_distincts,
            'max_training_pairs': 100,
            'recall_weight': 1.0,
            'fields': [],
            'selected_columns': selected_columns if selected_columns is not None and len(selected_columns) > 0 else None
        }

        # Run deduplication
        result = find_duplicates_in_files(
            file_paths=temp_files,
            config=config,
            training_data=training_data
        )

        if "pairs" in result:
            response_obj = {
                "status": "needs_training",
                "pairs": result["pairs"]
            }
        else:
            response_obj = {
                "status": "success",
                "duplicates": result
            }

        # Clean up temporary files
        for temp_file in temp_files:
            os.remove(temp_file)

        # Format response
        return JSONResponse(
            content=json.loads(json.dumps(response_obj, cls=NumpyEncoder))
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/")
async def root():
    return {"message": "API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        timeout_keep_alive=7200,  # 2 hours in seconds
        limit_concurrency=10,
        backlog=128
    )