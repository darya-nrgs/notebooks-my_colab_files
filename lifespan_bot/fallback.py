from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .schemas import AssistantQuestion, AssistantFinal, AssistantResponse


@dataclass
class Profile:
    age: Optional[float] = None
    sex: Optional[str] = None  # "مرد" or "زن"
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    smoker: Optional[bool] = None
    cigarettes_per_day: Optional[float] = None
    alcohol_per_week: Optional[float] = None  # standard drinks/week
    exercise_hours_per_week: Optional[float] = None
    sleep_hours: Optional[float] = None
    has_hypertension: Optional[bool] = None
    has_diabetes: Optional[bool] = None
    has_hyperlipidemia: Optional[bool] = None
    has_heart_disease: Optional[bool] = None
    parents_longevity: Optional[str] = None  # "هر دو >85" / "یکی >85" / "هیچ‌کدام"
    diet_score_1_to_5: Optional[int] = None
    stress_level_1_to_5: Optional[int] = None
    years_since_checkup: Optional[float] = None


def _to_bool(answer: str) -> Optional[bool]:
    a = answer.strip().lower()
    if a in {"بله", "بلی", "آره", "اره", "yes", "y"}:
        return True
    if a in {"خیر", "نه", "no", "n"}:
        return False
    return None


def _to_float(answer: str) -> Optional[float]:
    import re

    s = answer.strip().replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


@dataclass
class RuleBasedFallback:
    profile: Profile = field(default_factory=Profile)
    step_index: int = 0

    def _steps(self) -> List[str]:
        # Ordered list of step IDs
        return [
            "age",
            "sex",
            "height_weight",
            "smoking",
            "alcohol",
            "exercise",
            "sleep",
            "chronic",
            "family",
            "diet",
            "stress",
            "checkup",
        ]

    def next(self) -> AssistantResponse:
        steps = self._steps()
        if self.step_index >= len(steps):
            return self._final()
        sid = steps[self.step_index]
        if sid == "age":
            return AssistantQuestion(kind="question", question="سن شما چند سال است؟", choices=None)
        if sid == "sex":
            return AssistantQuestion(kind="question", question="جنس شما؟", choices=["مرد", "زن"])
        if sid == "height_weight":
            return AssistantQuestion(
                kind="question",
                question="قد (سانتی‌متر) و وزن (کیلوگرم) خود را بنویسید. مثال: 175، 72",
                choices=None,
            )
        if sid == "smoking":
            return AssistantQuestion(
                kind="question",
                question="آیا سیگار می‌کشید؟ اگر بله، حدود چند نخ در روز؟",
                choices=["خیر", "کم (۱-۵)", "متوسط (۶-۱۰)", "زیاد (>۱۰)"]
            )
        if sid == "alcohol":
            return AssistantQuestion(
                kind="question",
                question="مصرف الکل در هفته چند نوشیدنی استاندارد است؟",
                choices=["۰", "۱-۷", "۸-۱۴", ">۱۴"],
            )
        if sid == "exercise":
            return AssistantQuestion(
                kind="question",
                question="هفته‌ای چند ساعت فعالیت بدنی متوسط تا شدید دارید؟",
                choices=["۰", "۱-۲", "۳-4", "۵ یا بیشتر"],
            )
        if sid == "sleep":
            return AssistantQuestion(
                kind="question",
                question="به طور معمول، شب‌ها چند ساعت می‌خوابید؟",
                choices=["<5", "5-6", "7-9", ">9"],
            )
        if sid == "chronic":
            return AssistantQuestion(
                kind="question",
                question="آیا هر یک از موارد زیر را دارید؟ دیابت، فشارخون، چربی خون، بیماری قلبی (ذکر کنید)",
                choices=["هیچ‌کدام", "یکی", "چند مورد"],
            )
        if sid == "family":
            return AssistantQuestion(
                kind="question",
                question="طول‌عمر والدین/خانواده نزدیک چگونه بوده است؟",
                choices=["هر دو >85", "یکی >85", "هیچ‌کدام"],
            )
        if sid == "diet":
            return AssistantQuestion(
                kind="question",
                question="الگوی تغذیه (۱ خیلی ضعیف تا ۵ خیلی سالم)؟",
                choices=["1", "2", "3", "4", "5"],
            )
        if sid == "stress":
            return AssistantQuestion(
                kind="question",
                question="سطح استرس (۱ کم تا ۵ زیاد)؟",
                choices=["1", "2", "3", "4", "5"],
            )
        if sid == "checkup":
            return AssistantQuestion(
                kind="question",
                question="آخرین چکاپ پزشکی شما چند سال پیش بوده است؟",
                choices=["<1", "1-3", "3-7", ">7"],
            )
        return self._final()

    def ingest(self, answer: str) -> None:
        steps = self._steps()
        if self.step_index >= len(steps):
            return
        sid = steps[self.step_index]
        a = answer.strip()
        if sid == "age":
            self.profile.age = _to_float(a)
        elif sid == "sex":
            if "مرد" in a:
                self.profile.sex = "مرد"
            elif "زن" in a:
                self.profile.sex = "زن"
        elif sid == "height_weight":
            import re
            nums = [n for n in re.findall(r"-?\d+(?:\.\d+)?", a.replace(",", "."))]
            if len(nums) >= 2:
                self.profile.height_cm = float(nums[0])
                self.profile.weight_kg = float(nums[1])
        elif sid == "smoking":
            b = _to_bool(a)
            if b is not None:
                self.profile.smoker = b
            if self.profile.smoker:
                cigs = _to_float(a)
                self.profile.cigarettes_per_day = cigs if cigs is not None else 5.0
            elif b is False:
                self.profile.cigarettes_per_day = 0.0
        elif sid == "alcohol":
            val = _to_float(a)
            if val is None:
                if ">14" in a or ">۱۴" in a:
                    val = 15.0
                elif "8-14" in a or "۸-۱۴" in a:
                    val = 10.0
                elif "1-7" in a or "۱-۷" in a:
                    val = 4.0
                elif "0" in a or "۰" in a:
                    val = 0.0
            self.profile.alcohol_per_week = val
        elif sid == "exercise":
            val = _to_float(a)
            if val is None:
                if "۵" in a or "5" in a:
                    val = 5.0
                elif "3-4" in a or "۳-4" in a or "۳-۴" in a:
                    val = 3.5
                elif "1-2" in a or "۱-۲" in a:
                    val = 1.5
                elif "۰" in a or "0" in a:
                    val = 0.0
            self.profile.exercise_hours_per_week = val
        elif sid == "sleep":
            val = _to_float(a)
            if val is None:
                if ">9" in a or ">۹" in a:
                    val = 9.5
                elif "7-9" in a or "۷-۹" in a:
                    val = 8.0
                elif "5-6" in a or "۵-۶" in a:
                    val = 5.5
                elif "<5" in a:
                    val = 4.5
            self.profile.sleep_hours = val
        elif sid == "chronic":
            txt = a
            has_any = any(word in txt for word in ["دیابت", "فشار", "چربی", "قلب"])
            if not has_any and ("هیچ" in txt or "ندارم" in txt):
                self.profile.has_diabetes = False
                self.profile.has_hypertension = False
                self.profile.has_hyperlipidemia = False
                self.profile.has_heart_disease = False
            else:
                self.profile.has_diabetes = "دیابت" in txt or self.profile.has_diabetes
                self.profile.has_hypertension = "فشار" in txt or self.profile.has_hypertension
                self.profile.has_hyperlipidemia = "چربی" in txt or self.profile.has_hyperlipidemia
                self.profile.has_heart_disease = "قلب" in txt or self.profile.has_heart_disease
        elif sid == "family":
            if "هر دو" in a:
                self.profile.parents_longevity = "هر دو >85"
            elif "یکی" in a:
                self.profile.parents_longevity = "یکی >85"
            else:
                self.profile.parents_longevity = "هیچ‌کدام"
        elif sid == "diet":
            val = None
            try:
                val = int(_to_float(a) or 0)
            except Exception:
                pass
            if val is not None:
                self.profile.diet_score_1_to_5 = max(1, min(5, val))
        elif sid == "stress":
            val = None
            try:
                val = int(_to_float(a) or 0)
            except Exception:
                pass
            if val is not None:
                self.profile.stress_level_1_to_5 = max(1, min(5, val))
        elif sid == "checkup":
            val = _to_float(a)
            if val is None:
                if ">7" in a or ">۷" in a:
                    val = 8.0
                elif "3-7" in a or "۳-۷" in a:
                    val = 5.0
                elif "1-3" in a or "۱-۳" in a:
                    val = 2.0
                else:
                    val = 0.5
            self.profile.years_since_checkup = val
        self.step_index += 1

    def _bmi(self) -> Optional[float]:
        if self.profile.height_cm and self.profile.weight_kg:
            m = self.profile.height_cm / 100.0
            if m > 0:
                return self.profile.weight_kg / (m * m)
        return None

    def _final(self) -> AssistantFinal:
        p = self.profile
        # Base expected lifespan
        base = 85.0
        if p.sex == "مرد":
            base -= 3.0
        # BMI adjustments
        bmi = self._bmi()
        if bmi is not None:
            if 18.5 <= bmi <= 24.9:
                base += 1.0
            elif 25.0 <= bmi <= 29.9:
                base -= 1.0
            elif bmi >= 30.0:
                base -= 3.0
            elif bmi < 18.5:
                base -= 1.0
        # Smoking
        if p.smoker:
            base -= 7.0
            if p.cigarettes_per_day:
                base -= min(5.0, p.cigarettes_per_day * 0.1)
        # Alcohol
        if p.alcohol_per_week is not None:
            if p.alcohol_per_week > 14:
                base -= 2.0
            elif 8 <= p.alcohol_per_week <= 14:
                base -= 1.0
        # Exercise
        if p.exercise_hours_per_week is not None:
            if p.exercise_hours_per_week >= 5:
                base += 2.0
            elif 2 <= p.exercise_hours_per_week < 5:
                base += 1.0
            elif p.exercise_hours_per_week == 0:
                base -= 1.0
        # Sleep
        if p.sleep_hours is not None:
            if 7 <= p.sleep_hours <= 9:
                base += 1.0
            elif 5 <= p.sleep_hours < 7:
                base -= 1.0
            elif p.sleep_hours < 5:
                base -= 2.0
            elif p.sleep_hours > 9:
                base -= 1.0
        # Chronic conditions
        for flag, penalty in [
            (p.has_diabetes, 2.0),
            (p.has_hypertension, 1.0),
            (p.has_hyperlipidemia, 0.5),
            (p.has_heart_disease, 3.0),
        ]:
            if flag:
                base -= penalty
        # Family history
        if p.parents_longevity == "هر دو >85":
            base += 2.0
        elif p.parents_longevity == "یکی >85":
            base += 1.0
        elif p.parents_longevity == "هیچ‌کدام":
            base -= 0.5
        # Diet
        if p.diet_score_1_to_5 is not None:
            if p.diet_score_1_to_5 >= 4:
                base += 1.0
            elif p.diet_score_1_to_5 <= 2:
                base -= 1.0
        # Stress
        if p.stress_level_1_to_5 is not None:
            if p.stress_level_1_to_5 >= 5:
                base -= 2.0
            elif p.stress_level_1_to_5 == 4:
                base -= 1.0
            elif p.stress_level_1_to_5 == 1:
                base += 0.5
        # Checkup
        if p.years_since_checkup is not None:
            if p.years_since_checkup > 7:
                base -= 1.0
            elif p.years_since_checkup > 3:
                base -= 0.5

        # Clamp to reasonable range
        base = max(55.0, min(95.0, base))

        # If age is known, ensure final > current age by a small margin
        if p.age is not None:
            base = max(p.age + 5.0, base)

        # Confidence based on answered steps
        total_steps = len(self._steps())
        answered = min(self.step_index, total_steps)
        confidence = 0.5 + 0.4 * (answered / total_steps)
        confidence = min(0.95, max(0.5, confidence))

        reasoning = "برآورد تقریبی بر اساس سن، عادات سبک زندگی، وضعیت مزمن و سابقه خانوادگی."
        advice = (
            "این یک تخمین تقریبی است و جایگزین توصیه پزشکی نیست. "
            "ورزش منظم، تغذیه سالم، ترک سیگار، خواب کافی، مدیریت استرس و چکاپ دوره‌ای کمک‌کننده‌اند."
        )
        return AssistantFinal(
            kind="final",
            lifespanEstimate=round(float(base), 1),
            confidence=round(float(confidence), 2),
            reasoning=reasoning,
            advice=advice,
        )
