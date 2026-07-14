import json
from typing import Any


def build_feature_selection_prompt_payload(car_context: dict[str, Any]) -> dict[str, Any]:
    option_context = car_context.get("option_context") or {}
    metadata = option_context.get("metadata") or {}

    applied_options_payload = []
    for item in option_context.get("applied_options") or []:
        if not isinstance(item, dict):
            continue
        applied_options_payload.append(
            {
                "source_option_code": item.get("code"),
                "source_option_name": item.get("source_name"),
                "category": item.get("category"),
                "is_applied": bool(item.get("is_applied")),
            }
        )

    return {
        "vehicle_metadata": {
            "manufacturer": metadata.get("manufacturer") or car_context.get("manufacturer"),
            "model_group": metadata.get("model_group") or metadata.get("model") or car_context.get("model"),
            "exact_model": metadata.get("model") or car_context.get("model"),
            "grade": metadata.get("grade") or car_context.get("grade"),
            "grade_detail": metadata.get("grade_detail") or car_context.get("grade_detail"),
            "model_year": car_context.get("year"),
            "drivetrain_designation": metadata.get("drivetrain_designation") or car_context.get("drivetrain_designation"),
            "detail_query_car_id": option_context.get("detail_query_car_id"),
            "vehicle_id": option_context.get("vehicle_id"),
        },
        "applied_options": applied_options_payload,
        "secondary_main_options": list(option_context.get("main_options") or []),
        "incomplete_data": bool(option_context.get("is_incomplete")),
        "incomplete_reason": option_context.get("incomplete_reason"),
        "pricing_context": {
            "final_price_eur": car_context.get("final_price_eur"),
            "year": car_context.get("year"),
            "mileage": car_context.get("mileage"),
        },
    }


def build_feature_selection_prompt(prompt_payload: dict[str, Any]) -> str:
    payload_json = json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    return f"""
Ти си експерт по продажби на премиум автомобили. Върни САМО валиден JSON и нищо друго.

Схема (строго):
{{
  "title": "",
  "fuel": "",
  "transmission": "",
  "headline_features": [
    {{
      "source_feature": "",
      "source_option_code": "",
      "display_name_bg": "",
      "reason": "",
      "confidence": "high"
    }}
  ],
  "additional_features": [
    {{
      "source_feature": "",
      "source_option_code": "",
      "display_name_bg": "",
      "reason": "",
      "confidence": "high"
    }}
  ]
}}

Правила за селекция:
- Основен източник са applied_options.
- secondary_main_options са вторичен източник и не могат да override-нат по-специфичен applied option.
- Избери най-силните, продаваеми и специфични за модела екстри.
- headline_features: точно 3, когато има поне 3 силни в източника; иначе по-малко.
- additional_features: обичайно 4-5; максимум 6 само ако всички са силни.
- Не добавяй слаби базови екстри само за бройка.
- Без дублиране на capability между headline_features и additional_features.
- Не измисляй нищо, което не може да се проследи до source_feature/source_option_code/структурни данни.

Model-relative деприоритизация:
- За модерни premium SUV (напр. GLE/X5/Q7/Cayenne/Range Rover):
  leather, heated front seats, smart key, basic navigation, basic parking sensors, basic LED са baseline и не трябва да изместват по-силни екстри.
- Ако има 360 камера, не избирай само rear camera.
- Ако има MULTIBEAM/Matrix/Laser/Pixel, не избирай basic LED.
- Ако има ventilated/massage seats, heated front seats е нисък приоритет.

Roof терминология:
- Ако източникът е panoramic/panorama/파노라마 и еквиваленти: display_name_bg = "Панорамен покрив".
- Ако е нормален sunroof/moonroof: display_name_bg = "Електрически люк".
- Никога не използвай "Слънчев покрив".

Manufacturer terminology:
- Запази: 4MATIC, quattro, xDrive, AIRMATIC, DISTRONIC, Burmester, MULTIBEAM LED, AMG Line, S line, M Sport.
- Не заменяй 4MATIC/quattro/xDrive с generic 4x4.

Забранени filler фрази:
- Премиум изпълнение
- Богато оборудване
- Отлична конфигурация
- Отлично оборудване
- Луксозно изпълнение
- Комфортен интериор
- Подходящ избор за внос
- Премиум автомобил
- Високо ниво на комфорт
- Богата конфигурация
- Комфортен кожен салон

Title:
- Фактическо и атрактивно име без излишно дублиране на годината.
- Запази generation/body when known (напр. W167, Coupe, Sportback).

Входни структурни данни:
{payload_json}
""".strip()
