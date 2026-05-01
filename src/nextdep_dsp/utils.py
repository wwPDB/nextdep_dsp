import os
import requests
from typing import Optional
from nextdep_dsp.deposition.models import Response


def upload_file_resumable(url: str, data: dict, file_path: str, token: str, uploaded_bytes: int = 0) -> Optional[Response]:

    CHUNK_SIZE = 8 * 1024 * 1024

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    if uploaded_bytes >= file_size:
        raise ValueError("uploaded_bytes is already greater than or equal to file size")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    latest_response = None

    with open(file_path, "rb") as fp:
        fp.seek(uploaded_bytes)

        while uploaded_bytes < file_size:
            chunk = fp.read(CHUNK_SIZE)
            if not chunk:
                break

            chunk_start = uploaded_bytes
            chunk_end = chunk_start + len(chunk) - 1

            chunk_headers = {
                **headers,
                "Content-Range": f"bytes {chunk_start}-{chunk_end}/{file_size}",
            }

            files = {
                "file": (file_name, chunk, "application/octet-stream"),
            }

            response = requests.post(
                url,
                headers=chunk_headers,
                data=data,
                files=files,
                timeout=120,
            )

            response.raise_for_status()
            latest_response = response

            uploaded_bytes = latest_response.json().get("uploadedBytes", chunk_end + 1)
            print(f"Uploaded {uploaded_bytes}/{file_size} bytes")

    return Response(latest_response.status_code, latest_response.reason, latest_response.json()) or None
