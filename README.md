# Dedupe Records API

A FastAPI-based REST API for identifying and managing duplicate records in CSV/Excel files using the DedupeIO library.

## Features

- Upload CSV/Excel files for deduplication
- Configure deduplication parameters
- Process files to identify duplicates
- Review and resolve duplicate pairs
- Download cleaned datasets
- Get summary reports

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`
Swagger documentation will be available at `http://localhost:8000/docs`

## API Endpoints

### File Management
- `POST /upload/` - Upload one or two CSV/Excel files
- `GET /files/{file_id}/preview` - Preview uploaded file contents

### Deduplication
- `POST /dedupe/configure/{file_id}` - Configure deduplication parameters
- `POST /dedupe/process/{file_id}` - Start deduplication process
- `GET /dedupe/status/{job_id}` - Check process status

### Review and Resolution
- `GET /duplicates/{file_id}` - Get list of identified duplicates
- `POST /duplicates/{file_id}/resolve` - Resolve duplicate pairs

### Results
- `GET /results/{file_id}/download` - Download cleaned dataset
- `GET /results/{file_id}/summary` - Get deduplication summary report

## Example Usage

1. Upload files:
```bash
curl -X POST "http://localhost:8000/upload/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@data1.csv" \
  -F "files=@data2.csv"
```

2. Configure deduplication:
```bash
curl -X POST "http://localhost:8000/dedupe/configure/{file_id}" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "similarity_threshold": 0.8,
    "fields_config": {
      "name": "String",
      "email": "String",
      "phone": "String"
    }
  }'
```

3. Start processing:
```bash
curl -X POST "http://localhost:8000/dedupe/process/{file_id}" \
  -H "accept: application/json"
```

## Notes

- Maximum file size: 100MB per file
- Supported formats: CSV, XLSX, XLS
- Files are stored temporarily and deleted after 30 days
- Processing time depends on file size and complexity 