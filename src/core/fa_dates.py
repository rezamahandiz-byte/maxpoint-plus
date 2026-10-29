"""Persian/Jalali date conversion and Persian digit normalization."""
from __future__ import annotations
from datetime import date

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
_WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]

# [Ch9] Pre-computed leap years for Jalali 1400-1499 (33-year cycle)
_JALALI_LEAP_YEARS = frozenset(
    {1401,1405,1409,1413,1417,1422,1426,1430,
     1434,1438,1442,1446,1450,1455,1459,1463,
     1467,1471,1475,1479,1483,1488,1492,1496}
)

def is_jalali_leap(jy: int) -> bool:
    """[Ch9] True if Jalali year jy is a leap year (366 days, Esfand has 30 days)."""
    return jy in _JALALI_LEAP_YEARS

def to_fa_digits(value):
    return str(value).translate(_FA)

def ascii_digits(value):
    return str(value or "").translate(_ASCII)

def gregorian_to_jalali(gy, gm, gd):
    g_days=[31,28,31,30,31,30,31,31,30,31,30,31]
    j_days=[31,31,31,31,31,31,30,30,30,30,30,30]
    gy2=gy-1600; gm2=gm-1; gd2=gd-1
    gdn=365*gy2+(gy2+3)//4-(gy2+99)//100+(gy2+399)//400
    for i in range(gm2): gdn += g_days[i]
    if gm2>1 and ((gy%4==0 and gy%100!=0) or gy%400==0): gdn += 1
    gdn += gd2; jdn=gdn-79; jnp=jdn//12053; jdn%=12053
    jy=979+33*jnp+4*(jdn//1461); jdn%=1461
    if jdn>=366: jy+=(jdn-1)//365; jdn=(jdn-1)%365
    jm=1
    for days in j_days:
        if jdn>=days: jdn-=days; jm+=1
        else: break
    return jy,jm,jdn+1

def jalali_to_gregorian(jy,jm,jd):
    jy,jm,jd=int(jy),int(jm),int(jd)
    if not (1<=jm<=12 and 1<=jd<=31): raise ValueError("تاریخ شمسی معتبر نیست.")
    jy0=jy; jy+=1595; days=-355668+365*jy+(jy//33)*8+(((jy%33)+3)//4)+jd
    if jm<7: days+=(jm-1)*31
    else: days+=(jm-7)*30+186
    gy=400*(days//146097); days%=146097
    if days>36524:
        gy+=100*((days-1)//36524); days=(days-1)%36524
        if days>=365: days+=1
    gy+=4*(days//1461); days%=1461
    if days>365:
        gy+=(days-1)//365; days=(days-1)%365
    gd=days+1; leap=(gy%4==0 and gy%100!=0) or gy%400==0
    mdays=[31,29 if leap else 28,31,30,31,30,31,31,30,31,30,31]; gm=1
    while gm<=12 and gd>mdays[gm-1]: gd-=mdays[gm-1]; gm+=1
    if gm>12: raise ValueError("تاریخ شمسی معتبر نیست.")
    out=date(gy,gm,gd)
    if gregorian_to_jalali(out.year,out.month,out.day)!=(jy0,jm,jd): raise ValueError("روز واردشده در این ماه شمسی معتبر نیست.")
    return out

def normalize_date(value):
    raw=ascii_digits(str(value or "").strip()).replace("/","-")
    parts=raw.split("-")
    if len(parts)!=3: raise ValueError("تاریخ را به شکل سال-ماه-روز وارد کن؛ مثال ۱۴۰۵-۰۸-۰۶.")
    try:
        y,m,d=map(int,parts)
        if 1200<=y<=1599: return jalali_to_gregorian(y,m,d).isoformat()
        return date(y,m,d).isoformat()
    except ValueError as exc: raise ValueError("تاریخ واردشده معتبر نیست.") from exc

def format_jalali(iso_date):
    d=date.fromisoformat(iso_date); y,m,day=gregorian_to_jalali(d.year,d.month,d.day)
    return f"{to_fa_digits(y)}-{to_fa_digits(f'{m:02d}')}-{to_fa_digits(f'{day:02d}')}"

def jalali_label(iso_date):
    d=date.fromisoformat(iso_date); y,m,day=gregorian_to_jalali(d.year,d.month,d.day)
    return f"{_WEEKDAYS[d.weekday()]}، {to_fa_digits(day)} { _MONTHS[m-1] } {to_fa_digits(y)}"


def parse_jalali_date(text):
    """[Ch9] Parse Jalali date in multiple formats with strict validation.
    Accepts YYYY-MM-DD or YYYY/MM/DD, with Persian or English digits.
    Returns a Python date object.
    """
    raw = ascii_digits(str(text or "").strip()).replace("/", "-")
    parts = raw.split("-")
    if len(parts) != 3:
        raise ValueError("تاریخ را به شکل سال-ماه-روز وارد کن.")
    try:
        y, m, d = map(int, parts)
    except ValueError:
        raise ValueError("اعداد تاریخ معتبر نیست.")
    if not (1200 <= y <= 1599):
        raise ValueError("سال شمسی باید بین ۱۲۰۰ تا ۱۵۹۹ باشد.")
    if not (1 <= m <= 12):
        raise ValueError("ماه باید بین ۱ تا ۱۲ باشد.")
    # [Ch9] Validate day with leap-year awareness
    max_day = 31 if m <= 6 else 30
    if m == 12 and not is_jalali_leap(y):
        max_day = 29  # Esfand has 29 days in non-leap years
    if not (1 <= d <= max_day):
        raise ValueError(f"روز باید بین ۱ تا {max_day} باشد.")
    return jalali_to_gregorian(y, m, d)


def academic_year_for_date(iso_date):
    """[Ch11] Iranian academic year for a given ISO date.
    Academic year starts on Mehr 1 (~September 23).
    Returns "1404-1405" format.
    """
    d = date.fromisoformat(iso_date)
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    if jm >= 7:  # Mehr (month 7) or later
        return f"{jy}-{jy+1}"
    else:
        return f"{jy-1}-{jy}"
