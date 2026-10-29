# MAXPOINT-Plus v0.7 — Build Fix

یک‌بار درست کن، همیشه راحت بیلد کن.

## دستور بیلد (از این به بعد فقط همین)

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

این اسکریپت خودش:
1. git و gh CLI را چک می‌کند (اگر نباشد، با winget نصب می‌کند)
2. اگر gh لاگین نباشد، `gh auth login --web` اجرا می‌کند
3. تغییرات را commit و push می‌کند
4. workflow بیلد GitHub Actions را اجرا می‌کند
5. صبر می‌کند تا بیلد تمام شود (۱۵-۳۰ دقیقه)
6. APK را در `%USERPROFILE%\Downloads\maxpoint-plus-build` ذخیره می‌کند
7. مسیر فایل نصب (arm64-v8a) را چاپ می‌کند

## خروجی مورد انتظار

- مسیر APK: `%USERPROFILE%\Downloads\maxpoint-plus-build`
- فایل نصب روی گوشی: `app-arm64-v8a-release.apk`

## پیش‌نیازها (یک‌بار)

- ویندوز 10/11
- Python 3.12+ (در PATH)
- GitHub account
- internet connection

## چه چیزی تغییر کرد (v0.7 build fix)

| فایل | تغییر |
|------|-------|
| `pyproject.toml` | حذف `flet-android-notifications` (نیاز به desugaring داشت) + اضافه `[tool.flet.app] path = "src"` |
| `src/services/notifier.py` | stub شده — همه توابع (`init`, `configure_reminders`, `show_test_notification` و غیره) را نگه داشت ولی no-op |
| `.github/workflows/build-apk.yml` | workflow تمیز بدون خطای quoting — `flet build apk --yes --module-name main --split-per-abi` |
| `build.ps1` | اسکریپت یک‌دستوری بیلد |
| `scripts/v07_smoke.py` | تست‌های نوتیفیکیشن به stub-validation تغییر کرد |

## چه چیزی حفظ شد

- هیچ فایلی در `src/ui/` تغییر نکرد (به‌جز هیچ — کاملاً دست‌نخورده)
- هیچ فایلی در `src/core/` تغییر نکرد
- `src/main.py` کاملاً دست‌نخورده
- `product`, `bundle_id`, `version` در pyproject.toml تغییر نکرد
- همه ۵ تب اپ (خانه، ثبت، تحلیل، اعلان‌ها، بیشتر) سر جای خودشان هستند
- تقویم شمسی، ساعت آنلاین، تایمر مطالعه، تحلیل، گزارش GPT — همه حفظ شدند

## محدودیت‌های شناخته‌شده

- **نوتیفیکیشن بومی اندروید در این نسخه غیرفعال است.** تب «اعلان‌ها» هنوز در اپ هست و تنظیمات را ذخیره می‌کند، ولی اعلان واقعی روی گوشی نمایش داده نمی‌شود.
- **دلیل:** `flet-android-notifications` نیاز به Gradle core library desugaring دارد که Flet پیش‌فرض فعال نمی‌کند.
- **راه فعال‌سازی برای v0.8:** یک android project سفارشی با `coreLibraryDesugaringEnabled true` بساز (در `BUILD-APK-GUIDE.md` مسیر کامل نوشته شده).

## اجرای محلی (برای تست بدون بیلد APK)

```powershell
pip install 'flet[all]' flet-charts flet-secure-storage httpx
flet run src\main.py
```

## تست رگرسیون

```powershell
python scripts\v07_smoke.py
```

باید خروجی: `MAXPOINT Plus v0.7 regression: PASS`

## ساخت APK دستی (بدون build.ps1)

اگر خواستی دستی بیلد بگیری:

```powershell
# 1. keystore (یک‌بار)
keytool -genkey -v -keystore upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias maxpointplus

# 2. build
$env:FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD = 'رمز-keystore'
flet build apk --yes --module-name main --android-signing-key-store upload-keystore.jks --android-signing-key-alias maxpointplus --split-per-abi
```

APK در `build\android\` ساخته می‌شود.
