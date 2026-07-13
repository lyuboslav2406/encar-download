import uuid
import json

from .cleanup import cleanup_old_jobs
from .config import GENERATED_DIR
from .encar_options import (
    build_applied_option_evidence_block,
    build_main_options_evidence_block,
    extract_complete_option_context_from_detail_html,
)
from .image_service import create_zip, download_images
from .openai_service import build_facebook_post, generate_facebook_data_with_openai
from .pricing import (
    FRANKFURTER_SOURCE,
    calculate_final_price_eur,
    format_eur,
    format_km,
    get_eur_to_krw_rate_info,
    krw_to_eur_with_rate,
)
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
    (job_dir / "detail_page.html").write_text(html, encoding="utf-8")

    price_krw = extract_price_krw(html)
    car_year = extract_year(html)
    mileage = extract_mileage(html)

    krw_per_eur, exchange_rate_date = get_eur_to_krw_rate_info()
    base_price_eur = krw_to_eur_with_rate(price_krw, krw_per_eur)
    final_price_eur, extra_cost = calculate_final_price_eur(base_price_eur, car_year)

    clean_car_text = extract_clean_car_text(html)
    option_context = extract_complete_option_context_from_detail_html(html, url)

    debug_artifacts = option_context.get("debug_artifacts") or {}
    detail_preloaded_state = debug_artifacts.get("detail_preloaded_state")
    if detail_preloaded_state is not None:
        (job_dir / "detail_preloaded_state.json").write_text(
            json.dumps(detail_preloaded_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    option_page_html = debug_artifacts.get("option_page_html")
    if isinstance(option_page_html, str) and option_page_html:
        (job_dir / "option_page.html").write_text(option_page_html, encoding="utf-8")

    (job_dir / "all_option_entries.json").write_text(
        json.dumps(option_context.get("all_option_entries") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (job_dir / "applied_options.json").write_text(
        json.dumps(option_context.get("applied_options") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    applied_evidence = build_applied_option_evidence_block(option_context)
    main_options_evidence = build_main_options_evidence_block(option_context)

    ai_source_text = "\n".join(
        [
            "ПРИЛОЖЕНИ ОПЦИИ ОТ ENCAR OPTION PAGE:",
            applied_evidence,
            "",
            "КРАТЪК MAIN OPTIONS БЛОК (SECONDARY):",
            main_options_evidence,
            "",
            "ДОПЪЛНИТЕЛЕН ТЕКСТ ОТ ДЕТАЙЛ СТРАНИЦАТА:",
            clean_car_text,
        ]
    )

    print(
        "Encar option extraction diagnostics: "
        f"detail_query_car_id={option_context.get('detail_query_car_id')} "
        f"vehicle_id={option_context.get('vehicle_id')} "
        f"total_options_displayed={option_context.get('total_options_displayed')} "
        f"applied_options_count={option_context.get('applied_options_count')} "
        f"unresolved_option_count={len(option_context.get('unresolved_option_codes') or [])} "
        f"options_passed_to_ai_count={len(option_context.get('applied_options') or [])} "
        f"incomplete={option_context.get('is_incomplete')}"
    )

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
        "raw_car_text": clean_car_text,
        "ai_source_text": ai_source_text,
        "primary_option_evidence_block": applied_evidence,
        "main_options_evidence_block": main_options_evidence,
        "option_context": option_context,
        "manufacturer": (option_context.get("metadata") or {}).get("manufacturer"),
        "model": (option_context.get("metadata") or {}).get("model"),
        "grade": (option_context.get("metadata") or {}).get("grade"),
        "grade_detail": (option_context.get("metadata") or {}).get("grade_detail"),
        "drivetrain_designation": (option_context.get("metadata") or {}).get("drivetrain_designation"),
        "debug_dir": str(job_dir),
    }

    exchange_rate = {
        "source": FRANKFURTER_SOURCE,
        "date": exchange_rate_date,
        "base_currency": "EUR",
        "quote_currency": "KRW",
        "krw_per_eur": krw_per_eur,
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
        "exchange_rate": exchange_rate,
        "facebook_post": facebook_post,
        "zip_url": f"/download/{job_id}",
        "photos_url": f"/photos/{job_id}",
        "images_count": len(image_files)
    }


def process_price_summary(url: str):
    html = download_html(url)

    price_krw = extract_price_krw(html)
    car_year = extract_year(html)
    mileage = extract_mileage(html)

    krw_per_eur, exchange_rate_date = get_eur_to_krw_rate_info()
    base_price_eur = krw_to_eur_with_rate(price_krw, krw_per_eur)
    final_price_eur, extra_cost = calculate_final_price_eur(base_price_eur, car_year)

    price_summary = f"""Година: {car_year}
Пробег: {format_km(mileage)} km
Цена в Encar: {price_krw:,} KRW
Цена в Encar превалутирана в евро: {format_eur(round(base_price_eur))} €
Добавена доставка/комисионна: {format_eur(extra_cost)} €
Крайна цена до България: {format_eur(final_price_eur)} €""".replace(",", " ")

    return {
        "price_summary": price_summary,
        "exchange_rate": {
            "source": FRANKFURTER_SOURCE,
            "date": exchange_rate_date,
            "base_currency": "EUR",
            "quote_currency": "KRW",
            "krw_per_eur": krw_per_eur,
        },
    }
