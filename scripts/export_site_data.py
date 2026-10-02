"""Export anonymized aggregate survey data for the static dashboard site."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "oral_survey_app"
sys.path.insert(0, str(APP_DIR))

from core import AGES, Database, number, people, text  # noqa: E402


def add_binary(bucket, name, value, allowed=(0, 1), predicate=lambda v: v == 1):
    value = number(value)
    if value in allowed:
        bucket[name + "_den"] += 1
        bucket[name + "_num"] += int(predicate(value))


def export():
    data = Database(APP_DIR / "data").load()
    buckets = defaultdict(lambda: defaultdict(float))

    for age in AGES:
        parents = {
            text(row.get("รหัสรอบสำรวจโรงเรียน")): row
            for row in data[age].get("ข้อมูลโรงเรียน", [])
        }
        for row in people(data, age):
            parent = parents.get(text(row.get("รหัสรอบสำรวจโรงเรียน")), {})
            district = text(row.get("อำเภอ") or parent.get("อำเภอ")) or "ไม่ระบุ"
            tambon = text(row.get("ตำบล") or parent.get("ตำบล")) or "ไม่ระบุ"
            unit = text(row.get("โรงเรียนพื้นที่สุ่ม") or row.get("ชื่อสถานที่สำรวจจริง") or parent.get("ชื่อสถานที่สำรวจจริง")) or "ไม่ระบุ"
            year = text(row.get("ปีการศึกษา พ.ศ.") or row.get("ปีสำรวจ พ.ศ.") or row.get("_ปี")) or "ไม่ระบุ"
            bucket = buckets[(age, district, tambon, unit, year)]
            bucket["n"] += 1

            if age in ("3", "12"):
                keys = (("ฟันน้ำนมผุ d (ซี่)", "ฟันน้ำนมถอน m (ซี่)", "ฟันน้ำนมอุด f (ซี่)") if age == "3" else ("ฟันแท้ผุ D (ซี่)", "ฟันแท้ถอน M (ซี่)", "ฟันแท้อุด F (ซี่)"))
                values = [number(row.get(key)) for key in keys]
                limit = 20 if age == "3" else 32
                decay = values[0]
                if decay is not None and decay >= 0 and decay.is_integer() and decay <= limit:
                    bucket["cavity_den"] += 1
                    bucket["cavity_free"] += int(decay == 0)
                if all(v is not None and v >= 0 and v.is_integer() for v in values) and sum(values) <= limit:
                    bucket["dental_den"] += 1
                    bucket["dental_sum"] += sum(values)
                    bucket["caries"] += int(sum(values) > 0)
            if age == "3":
                add_binary(bucket, "white", row.get("พบรอยขาว White spot"))
            elif age == "12":
                add_binary(bucket, "fluor", row.get("ฟันตกกระ"))
                add_binary(bucket, "gum", row.get("เหงือกอักเสบ"))
                values = [number(row.get(k)) for k in ("แปรงฟันตอนเช้า", "แปรงฟันก่อนนอน", "แปรงฟัน 2 นาที/ครั้ง", "ไม่กินอาหารหลังแปรงฟัน 2 ชั่วโมง")]
                if all(v in (0, 1) for v in values):
                    bucket["brush_den"] += 1
                    bucket["brush_num"] += int(all(v == 1 for v in values))
            else:
                teeth = number(row.get("ฟันแท้ใช้งานได้ (ซี่)"))
                if teeth is not None and teeth >= 0 and teeth.is_integer():
                    bucket["teeth_den"] += 1; bucket["teeth_sum"] += teeth; bucket["teeth20"] += int(teeth >= 20)
                pair = number(row.get("คู่สบฟันหลัง"))
                if pair in (0, 1, 2, 3):
                    bucket["pair_den"] += 1; bucket[f"pair_{int(pair)}"] += 1
                add_binary(bucket, "loose", row.get("ฟันเทียม ความโยกหรือหลวม"), (0, 1, 9))

    output = []
    for key, metrics in sorted(buckets.items()):
        age, district, tambon, unit, year = key
        output.append({"age": age, "district": district, "tambon": tambon, "unit": unit, "year": year, **{k: int(v) if float(v).is_integer() else v for k, v in metrics.items()}})

    target = Path(__file__).resolve().parents[1] / "dist" / "data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "buckets": output}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"buckets": len(output), "records": sum(row["n"] for row in output), "target": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    export()
