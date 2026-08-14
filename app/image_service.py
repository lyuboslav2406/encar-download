import re
import zipfile
from pathlib import Path

import requests

from .config import GENERATED_DIR, HEADERS, MAX_IMAGES


def download_images(html, save_dir):
    matches = re.findall(r'https?:\\?/\\?/[^"\']+\.(?:jpg|jpeg|png)[^"\']*', html)

    images = []

    for match in matches:
        img_url = match.replace("\\/", "/")

        if "carpicture" not in img_url.lower():
            continue

        if img_url not in images:
            images.append(img_url)

    images = images[:MAX_IMAGES]
    saved_files = []

    for idx, img_url in enumerate(images, start=1):
        response = requests.get(img_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        file_path = save_dir / f"{idx:02d}.jpg"

        with open(file_path, "wb") as f:
            f.write(response.content)

        saved_files.append(file_path)

    return saved_files


def create_zip(files, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            zip_file.write(file, arcname=file.name)


def get_image_path(job_id: str, image_name: str) -> Path:
    return GENERATED_DIR / job_id / image_name
