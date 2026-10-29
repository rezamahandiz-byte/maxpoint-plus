"""Privacy-conscious AI reporting and deterministic offline reports."""
from __future__ import annotations
import json
from typing import Any
import httpx
from . import models

OPENAI_ENDPOINT = "https://gapgpt.app/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT_S = 45.0

async def request_report(report_type: str, summary: dict[str, Any], api_key: str,
                         endpoint: str | None = None, model: str | None = None) -> str:
    """Request an AI report using only aggregate stats (never raw rows/notes)."""
    key=(api_key or "").strip()
    if not key: raise ValueError("کلید API را در تنظیمات ذخیره کن یا موقتاً همین‌جا وارد کن.")
    url=(endpoint or OPENAI_ENDPOINT).strip()
    model_name=(model or OPENAI_MODEL).strip() or OPENAI_MODEL
    local_http = url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]"))
    if not url.startswith("https://") and not local_http:
        raise ValueError("برای حفاظت از کلید API از HTTPS استفاده کن؛ HTTP فقط برای آدرس محلی قابل قبول است.")
    system=(
        "تو تحلیلگر خصوصی مطالعه، زمان و عملکرد تحصیلی هستی. به فارسی روشن و دقیق پاسخ بده. "
        "فقط بر اساس اعداد ورودی نتیجه بگیر؛ داده ثبت‌نشده را صفر تلقی نکن؛ همبستگی را علت قطعی ندان. "
        "تفریح، کار و مسئولیت را خودکار اتلاف وقت معرفی نکن. وعده قطعی درباره رتبه/تراز آینده نده. "
        "خروجی با عنوان‌های: خلاصه، الگوهای قابل مشاهده، فاصله از برنامه، حداکثر سه اقدام مشخص. "
        "اطلاعات فقط آمار تجمیعی است؛ درباره داده‌هایی که وجود ندارند حدس نزن."
    )
    lower_model = model_name.lower()
    reasoning_family = lower_model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))
    token_param = "max_completion_tokens" if reasoning_family else "max_tokens"
    payload={"model": model_name, "messages":[
        {"role":"system", "content":system},
        {"role":"user", "content":"بر پایه‌ی این آمار تجمیعی گزارش تهیه کن:\n"+json.dumps(summary, ensure_ascii=False)},
    ], token_param: 1100}
    if not reasoning_family:
        payload["temperature"] = 0.35
    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_S) as client:
            response=await client.post(url, headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, json=payload)
            response.raise_for_status(); data=response.json()
    except httpx.TimeoutException as exc: raise RuntimeError("پاسخ API دیر رسید. دوباره تلاش کن؛ گزارش آفلاین همچنان در دسترس است.") from exc
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        if code in (401,403): raise RuntimeError("کلید API معتبر نیست یا دسترسی لازم را ندارد.") from exc
        if code == 429: raise RuntimeError("محدودیت درخواست یا اعتبار API فعال شده؛ وضعیت حساب را بررسی کن.") from exc
        detail=(exc.response.text or "")[:250]
        raise RuntimeError(f"خطای API ({code}): {detail}") from exc
    except httpx.HTTPError as exc: raise RuntimeError("اتصال به API برقرار نشد. اینترنت و نشانی سرویس را بررسی کن.") from exc
    try: content=data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc: raise RuntimeError("ساختار پاسخ API معتبر نیست.") from exc
    if isinstance(content, list): content="\n".join(str(p.get("text","")) for p in content if isinstance(p,dict))
    content=str(content or "").strip()
    if not content: raise RuntimeError("پاسخ مدل خالی بود.")
    return content

def build_local_report(summary: dict[str, Any]) -> str:
    """Generate a useful offline summary without any network call."""
    minutes=int(summary.get("total_recorded_minutes") or 0)
    tests=int(summary.get("tests") or 0)
    groups=summary.get("minutes_by_group") or []
    lines=["گزارش محلی MAXPOINT", f"بازه: {summary.get('period_start','')} تا {summary.get('period_end','')}", ""]
    lines.append(f"زمان ثبت‌شده: {minutes} دقیقه در {summary.get('active_days',0)} روز فعال.")
    lines.append(f"تعداد تست‌ها: {tests}؛ درست: {summary.get('correct',0)}؛ غلط: {summary.get('wrong',0)}؛ نزده: {summary.get('blank',0)}.")
    acc=summary.get("accuracy_percent")
    lines.append("دقت تست‌های پاسخ‌داده‌شده: " + (f"{acc}٪." if acc is not None else "هنوز برای محاسبه دقت، پاسخ درست/غلط کافی نیست."))
    lines.append(f"پوشش ثبت روزانه: {summary.get('data_quality_percent',0)}٪.")
    goal_rows = summary.get("goal_progress") or []
    if goal_rows:
        lines.append("\nفاصله از هدف‌های تعریف‌شده:")
        for goal in goal_rows[:8]:
            target = int(goal.get("target_minutes") or 0)
            actual = int(goal.get("actual_minutes") or 0)
            if target <= 0:
                continue
            gap = max(0, target - actual)
            progress = min(100, round(actual * 100 / target))
            lines.append(f"• {goal.get('activity', 'فعالیت')}، {goal.get('period', 'هدف')}: {actual}/{target} دقیقه ({progress}٪)، فاصله {gap} دقیقه.")
    lines.append("\nتوزیع زمان ثبت‌شده:")
    if groups:
        for item in groups:
            lines.append(f"• {item.get('group','سایر')}: {item.get('minutes',0)} دقیقه")
    else: lines.append("• در این بازه رکوردی برای نمایش وجود ندارد.")
    first,last=summary.get("exam_taraz_first"),summary.get("exam_taraz_last")
    if first is not None and last is not None:
        diff=int(last)-int(first)
        lines.append(f"\nروند تراز ثبت‌شده: از {first} به {last} ({'+' if diff>0 else ''}{diff}). این تغییر به‌تنهایی آینده را پیش‌بینی نمی‌کند.")
    lines.append("\nاقدام پیشنهادی: ابتدا کیفیت ثبت را بررسی کن؛ سپس روی یک تغییر کوچک و قابل سنجش در برنامه‌ی هفته‌ی بعد تمرکز کن.")
    lines.append("\nاین گزارش فقط از آمار موجود استفاده می‌کند؛ زمان ثبت‌نشده به معنای فعالیت صفر نیست.")
    return "\n".join(lines)
