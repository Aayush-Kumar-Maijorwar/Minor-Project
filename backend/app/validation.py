"""
Input validation. Out-of-range or invalid VALUES are a hard error (422, field named,
value never clipped) - a clinician typo must not silently become a wrong prediction.
A MISSING field or an unusable FILE is a different thing: that model simply does not
run and the condition becomes not_assessed with a reason (handled in registry.py /
main.py, not here).
"""
from fastapi import HTTPException

ALLOWED_SEX = {"Female", "Male", "Other"}
ALLOWED_SMOKING_HISTORY = {"never", "former", "current", "not current", "ever", "No Info"}

ECG_REQUIRED_LEN = 187
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MIN_IMAGE_SIDE = 32


def _check_range(field: str, value: float, lo: float, hi: float):
    if value is None:
        return
    if not (lo <= value <= hi):
        raise HTTPException(status_code=422, detail=f"{field} must be between {lo} and {hi} (got {value})")


def validate_clinical_fields(
    age: float | None = None,
    sex: str | None = None,
    bmi: float | None = None,
    smoking_history: str | None = None,
):
    _check_range("age", age, 0, 120)
    _check_range("bmi", bmi, 10, 70)
    if sex is not None and sex not in ALLOWED_SEX:
        raise HTTPException(status_code=422, detail=f"sex must be one of {sorted(ALLOWED_SEX)} (got {sex!r})")
    if smoking_history is not None and smoking_history not in ALLOWED_SMOKING_HISTORY:
        raise HTTPException(
            status_code=422,
            detail=f"smoking_history must be one of {sorted(ALLOWED_SMOKING_HISTORY)} (got {smoking_history!r})",
        )


def validate_lab_fields(hba1c: float | None = None, blood_glucose: float | None = None):
    _check_range("hba1c", hba1c, 3, 15)
    _check_range("blood_glucose", blood_glucose, 40, 600)
