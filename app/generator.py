import uuid

from .cleanup import cleanup_old_jobs
from .config import GENERATED_DIR
from .image_service import create_zip, download_images
from .openai_service import build_facebook_post, generate_facebook_data_with_openai
from .pricing import calculate_final_price_eur, format_eur, format_km, krw_to_eur
from .scraper import (
    download_html,
    extract_clean_car_text,
    extract_mileage,
    extract_price_krw,
    extract_year,
)


def process_encar(url: str):
    cleanup_old_jobs(max_age_hours=24, max_jobs=30)
    job_id = str(uuid.uuid4())
    job_dir = GENERATED_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    html = download_html(url)

    price_krw = extract_price_krw(html)
    car_year = extract_year(html)
    mileage = extract_mileage(html)

    base_price_eur = krw_to_eur(price_krw)
    final_price_eur, extra_cost = calculate_final_price_eur(base_price_eur, car_year)

    clean_car_text = extract_clean_car_text(html)

    car_context = {
        "url": url,
        "year": car_year,
        "mileage": mileage,
        "price_krw": price_krw,
        "base_price_eur": round(base_price_eur),
        "extra_cost_eur": extra_cost,
        "final_price_eur": final_price_eur,
        "formatted_base_price_eur": format_eur(round(base_price_eur)),
        "formatted_final_price_eur": format_eur(final_price_eur),
        "formatted_mileage": format_km(mileage),
        "raw_car_text": clean_car_text
    }

    vehicle_data = generate_facebook_data_with_openai(car_context)
    facebook_post = build_facebook_post(car_context, vehicle_data)

    image_files = download_images(html, job_dir)
    zip_path = job_dir / "encar_images.zip"
    create_zip(image_files, zip_path)

    price_summary = f"""━━━━━━━━━━━━━━━━━━━
Година: {car_year}
Пробег: {format_km(mileage)} km
Цена в Encar: {price_krw:,} KRW
Цена в Encar, превалутирана в евро: {format_eur(round(base_price_eur))} €
Добавена доставка/комисионна: {format_eur(extra_cost)} €
Крайна цена до България: {format_eur(final_price_eur)} €
━━━━━━━━━━━━━━━━━━━""".replace(",", " ")

    return {
        "job_id": job_id,
        "price_summary": price_summary,
        "facebook_post": facebook_post,
        "zip_url": f"/download/{job_id}",
        "photos_url": f"/photos/{job_id}",
        "images_count": len(image_files)
    }
