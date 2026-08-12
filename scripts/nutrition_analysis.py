#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜品营养分析引擎 - nutrition_analysis.py
适用于高校食堂美团外卖点餐场景

功能模式:
  single   - 单道菜品营养查询
  daily    - 单日营养汇总分析
  weekly   - 一周营养综合分析与建议
  recommend - 基于营养缺口推荐菜品
  search   - 按关键词搜索菜品
  category - 按分类列出菜品
  menu     - 生成一餐/一日的营养报告（带缺口分析）

数据来源:
  - 菜品数据库: data/dishes_nutrition.json (1152道)
  - DRIs 2023: references/dris_2023.json
"""

import json
import os
import sys
import re
from datetime import datetime

# ============================================================
# 路径与数据加载
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_PATH = os.path.join(SKILL_DIR, "data", "dishes_nutrition.json")
DRIS_PATH = os.path.join(SKILL_DIR, "references", "dris_2023.json")

_nutrition_db = None
_dris = None

def load_db():
    global _nutrition_db
    if _nutrition_db is None:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _nutrition_db = json.load(f)
    return _nutrition_db

def load_dris():
    global _dris
    if _dris is None:
        with open(DRIS_PATH, "r", encoding="utf-8") as f:
            _dris = json.load(f)
    return _dris


# ============================================================
# 菜品匹配引擎（模糊搜索）
# ============================================================

def find_dish(name):
    """精确或模糊匹配菜品名，返回菜品记录"""
    db = load_db()
    name = name.strip()
    # 精确匹配
    for d in db:
        if d["name"] == name:
            return d, 1.0
    # 包含匹配
    matches = []
    for d in db:
        if name in d["name"] or d["name"] in name:
            matches.append((d, 0.8))
    if matches:
        # 返回最短的（最精确的）
        matches.sort(key=lambda x: len(x[0]["name"]))
        return matches[0]
    # 逐字匹配
    chars = set(name)
    scored = []
    for d in db:
        d_chars = set(d["name"])
        overlap = len(chars & d_chars)
        score = overlap / max(len(chars), len(d_chars))
        if score >= 0.5:
            scored.append((d, score))
    if scored:
        scored.sort(key=lambda x: -x[1])
        return scored[0]
    return None, 0.0

def find_dishes(names):
    """批量匹配菜品，返回 [(dish_record, matched_name, confidence), ...]"""
    results = []
    for name in names:
        dish, conf = find_dish(name)
        results.append((dish, name, conf))
    return results


# ============================================================
# 营养素参考值提取
# ============================================================

def get_reference(gender="male"):
    """获取DRIs参考值，gender: male/female"""
    dris = load_dris()
    key = "male_18_24" if gender == "male" else "female_18_24"
    ref = dris[key]
    return ref

# 营养素中文名映射
NUTRIENT_LABELS = {
    "kcal":       ("能量",     "kcal"),
    "protein":    ("蛋白质",   "g"),
    "fat":        ("脂肪",     "g"),
    "carb":       ("碳水化合物","g"),
    "fiber":      ("膳食纤维", "g"),
    "na":         ("钠",       "mg"),
    "ca":         ("钙",       "mg"),
    "fe":         ("铁",       "mg"),
    "zn":         ("锌",       "mg"),
    "va":         ("维生素A",  "μgRAE"),
    "vc":         ("维生素C",  "mg"),
    "chol":       ("胆固醇",   "mg"),
}

# DRIs key → 营养素key映射
DRIS_MAP = {
    "kcal":    ("energy", "rni"),
    "protein": ("protein", "rni"),
    "fiber":   ("fiber", "ai"),
    "na":      ("sodium", "pi"),
    "ca":      ("calcium", "rni"),
    "fe":      ("iron", "rni"),
    "zn":      ("zinc", "rni"),
    "va":      ("vitamin_a", "rni"),
    "vc":      ("vitamin_c", "rni"),
    "chol":    ("cholesterol", "pi"),
}


def get_dri_value(nutrient_key, gender="male"):
    """获取某营养素的DRIs推荐值"""
    ref = get_reference(gender)
    # 脂肪: AMDR 20-30%E，取中值25%E换算为克
    if nutrient_key == "fat":
        energy = ref["energy"]["rni"]
        return round(energy * 0.25 / 9, 1)  # 25%能量来自脂肪，9kcal/g
    # 碳水: AMDR 50-65%E，取中值55%E换算为克
    if nutrient_key == "carb":
        energy = ref["energy"]["rni"]
        return round(energy * 0.55 / 4, 1)  # 55%能量来自碳水，4kcal/g
    if nutrient_key not in DRIS_MAP:
        return None
    cat, field = DRIS_MAP[nutrient_key]
    if cat in ref and field in ref[cat]:
        return ref[cat][field]
    # 回退到AI
    if cat in ref and "ai" in ref[cat]:
        return ref[cat]["ai"]
    return None


def get_dri_ul(nutrient_key, gender="male"):
    """获取某营养素的UL（可耐受最高摄入量）"""
    ref = get_reference(gender)
    mapping = {
        "na": ("sodium", "ul"),
        "ca": ("calcium", "ul"),
        "fe": ("iron", "ul"),
        "zn": ("zinc", "ul"),
        "va": ("vitamin_a", "ul"),
        "vc": ("vitamin_c", "ul"),
    }
    if nutrient_key in mapping:
        cat, field = mapping[nutrient_key]
        if cat in ref and field in ref[cat]:
            return ref[cat][field]
    return None


# ============================================================
# 营养等级评估
# ============================================================

def assess_grade(percentage):
    """根据占日参考量百分比给出评级"""
    if percentage >= 100:
        return "充足"
    elif percentage >= 70:
        return "较好"
    elif percentage >= 40:
        return "偏低"
    elif percentage > 0:
        return "不足"
    else:
        return "缺失"


# ============================================================
# 模式1: 单道菜品营养查询
# ============================================================

def mode_single(dish_name, gender="male", meal_type="lunch"):
    """单道菜品营养分析"""
    dish, conf = find_dish(dish_name)
    if not dish:
        return {"error": f"未找到菜品: {dish_name}"}

    ref = get_reference(gender)
    result = {
        "dish": dish,
        "confidence": conf,
        "gender": gender,
        "meal_type": meal_type,
        "analysis": {}
    }

    # 计算每道菜占日参考量的百分比
    for nkey in ["kcal", "protein", "fat", "fiber", "na", "ca", "fe", "zn", "va", "vc"]:
        value = dish.get(nkey, 0)
        dri = get_dri_value(nkey, gender)
        if dri and dri > 0:
            pct = round(value / dri * 100, 1)
        else:
            pct = 0
        label, unit = NUTRIENT_LABELS.get(nkey, (nkey, ""))
        grade = assess_grade(pct)

        # 钠特殊处理：占PI百分比
        if nkey == "na":
            pi = get_dri_value("na", gender) or 2000
            pct = round(value / pi * 100, 1)
            if pct > 33:
                grade = "偏高" if pct > 50 else "较高"
            else:
                grade = "适宜"

        result["analysis"][nkey] = {
            "value": value,
            "unit": unit,
            "daily_pct": pct,
            "grade": grade,
            "dri": dri,
        }

    # 钠含量警示
    na = dish.get("na", 0)
    if na > 800:
        result["sodium_warning"] = f"本菜钠含量 {na}mg，偏高，建议搭配低钠菜品"
    elif na > 500:
        result["sodium_warning"] = f"本菜钠含量 {na}mg，中等偏高，注意全天钠摄入"

    # 过敏原
    if dish.get("allergens") and dish["allergens"] != "无":
        result["allergen_warning"] = f"含过敏原: {dish['allergens']}"

    # 膳食建议
    result["advice"] = dish.get("advice", "")
    result["grade"] = dish.get("grade", "")

    return result


# ============================================================
# 模式2: 单日营养汇总
# ============================================================

def aggregate_nutrition(dishes):
    """汇总多道菜品的营养"""
    totals = {"kcal": 0, "protein": 0, "fat": 0, "carb": 0, "fiber": 0,
              "na": 0, "ca": 0, "fe": 0, "zn": 0, "va": 0, "vc": 0, "chol": 0}
    for d in dishes:
        for k in totals:
            totals[k] += d.get(k, 0)
    return totals


def mode_daily(dishes_input, gender="male"):
    """单日营养汇总分析
    dishes_input: list of dish name strings
    """
    matched = find_dishes(dishes_input)
    found = [(d, n, c) for d, n, c in matched if d is not None]
    not_found = [n for d, n, c in matched if d is None]

    if not found:
        return {"error": "未匹配到任何菜品", "input": dishes_input}

    dishes = [item[0] for item in found]
    totals = aggregate_nutrition(dishes)

    # 对比日参考量
    comparison = {}
    for nkey in ["kcal", "protein", "fat", "fiber", "na", "ca", "fe", "zn", "va", "vc", "chol"]:
        value = totals.get(nkey, 0)
        dri = get_dri_value(nkey, gender)
        if dri and dri > 0:
            pct = round(value / dri * 100, 1)
        else:
            pct = 0
        label, unit = NUTRIENT_LABELS.get(nkey, (nkey, ""))

        # 判定状态
        if nkey == "na":
            if pct > 100:
                status = "超标"
            elif pct > 80:
                status = "偏高"
            elif pct > 50:
                status = "适宜"
            else:
                status = "偏低"
        elif nkey == "chol":
            if pct > 100:
                status = "超标"
            elif pct > 70:
                status = "偏高"
            else:
                status = "适宜"
        elif nkey in ["kcal", "protein"]:
            if pct >= 100:
                status = "达标"
            elif pct >= 70:
                status = "偏低"
            else:
                status = "不足"
        elif nkey == "fat":
            if pct > 120:
                status = "超标"
            elif pct > 80:
                status = "偏高"
            else:
                status = "适宜"
        else:
            if pct >= 100:
                status = "达标"
            elif pct >= 70:
                status = "较好"
            elif pct >= 40:
                status = "偏低"
            else:
                status = "不足"

        comparison[nkey] = {
            "total": value,
            "unit": unit,
            "dri": dri,
            "pct": pct,
            "status": status,
            "gap": round(dri - value, 1) if dri else None,
        }

    # 食物多样性
    categories = set(d["category"] for d in dishes)
    food_types = len(categories)

    # 食物多样性评估
    if food_types >= 4:
        diversity_grade = "优秀"
    elif food_types >= 3:
        diversity_grade = "良好"
    elif food_types >= 2:
        diversity_grade = "一般"
    else:
        diversity_grade = "单一"

    # 蔬菜量评估
    veg_dishes = [d for d in dishes if d["category"] == "蔬菜菌菇类"]
    veg_weight = sum(d["weight"] for d in veg_dishes)

    # 营养缺口
    gaps = []
    for nkey, info in comparison.items():
        if info["status"] in ["不足", "偏低"]:
            gaps.append({
                "nutrient": NUTRIENT_LABELS.get(nkey, (nkey, ""))[0],
                "key": nkey,
                "current": info["total"],
                "needed": info["dri"],
                "gap": info["gap"],
                "unit": info["unit"],
            })

    return {
        "matched_dishes": [{"name": d["name"], "category": d["category"],
                             "kcal": d["kcal"], "grade": d["grade"]}
                            for d, n, c in found],
        "not_found": not_found,
        "total_dishes": len(dishes),
        "totals": totals,
        "comparison": comparison,
        "food_diversity": {
            "categories": list(categories),
            "types": food_types,
            "grade": diversity_grade,
        },
        "vegetable_intake": {
            "dishes": len(veg_dishes),
            "weight_g": veg_weight,
            "target_g": 300,
            "status": "达标" if veg_weight >= 300 else f"差{300 - veg_weight}g",
        },
        "nutrition_gaps": gaps,
        "recommendation_hint": "根据营养缺口，建议搭配以下类型菜品" if gaps else "营养摄入较均衡",
    }


# ============================================================
# 模式3: 一周营养综合分析
# ============================================================

def mode_weekly(weekly_data, gender="male"):
    """一周营养综合分析
    weekly_data: {
        "gender": "male",
        "days": [
            {"date": "2026-08-11", "dishes": ["鱼香肉丝", "番茄炒蛋", ...]},
            ...
        ]
    }
    """
    days = weekly_data.get("days", [])
    gender = weekly_data.get("gender", gender)

    if not days:
        return {"error": "无每日数据"}

    daily_results = []
    all_dishes = []
    daily_totals = []
    daily_gaps = []
    daily_sodium = []
    daily_kcal = []
    daily_protein = []
    breakfast_count = 0
    categories_all = set()
    no_veg_days = 0

    for day in days:
        date = day.get("date", "未知")
        dish_names = day.get("dishes", [])
        meal = day.get("meal_type", "")

        result = mode_daily(dish_names, gender)
        if "error" in result:
            daily_results.append({"date": date, "error": result["error"]})
            continue

        daily_results.append({
            "date": date,
            "dish_count": result["total_dishes"],
            "kcal": result["totals"]["kcal"],
            "protein": result["totals"]["protein"],
            "na": result["totals"]["na"],
            "diversity": result["food_diversity"]["grade"],
            "veg_status": result["vegetable_intake"]["status"],
            "gaps_count": len(result["nutrition_gaps"]),
        })

        daily_totals.append(result["totals"])
        daily_gaps.extend(result["nutrition_gaps"])
        daily_sodium.append(result["totals"]["na"])
        daily_kcal.append(result["totals"]["kcal"])
        daily_protein.append(result["totals"]["protein"])
        categories_all.update(result["food_diversity"]["categories"])
        all_dishes.extend(dish_names)

        if day.get("has_breakfast"):
            breakfast_count += 1
        if result["vegetable_intake"]["dishes"] == 0:
            no_veg_days += 1

    n = len(daily_totals)
    if n == 0:
        return {"error": "无可分析的天数"}

    avg = {}
    for key in daily_totals[0]:
        avg[key] = round(sum(d[key] for d in daily_totals) / n, 1)

    # 周平均 vs 日参考量
    weekly_comparison = {}
    for nkey in ["kcal", "protein", "fat", "fiber", "na", "ca", "fe", "zn", "va", "vc"]:
        avg_val = avg.get(nkey, 0)
        dri = get_dri_value(nkey, gender)
        if dri and dri > 0:
            pct = round(avg_val / dri * 100, 1)
        else:
            pct = 0
        label, unit = NUTRIENT_LABELS.get(nkey, (nkey, ""))

        if nkey == "na":
            if pct > 100:
                status = "超标"
            elif pct > 80:
                status = "偏高"
            else:
                status = "适宜"
        elif nkey == "fat":
            if pct > 120:
                status = "超标"
            elif pct > 90:
                status = "偏高"
            elif pct > 0:
                status = "适宜"
            else:
                status = "不足"
        elif nkey in ["kcal", "protein"]:
            if pct >= 90:
                status = "达标"
            elif pct >= 70:
                status = "偏低"
            else:
                status = "不足"
        else:
            if pct >= 80:
                status = "达标"
            elif pct >= 50:
                status = "偏低"
            else:
                status = "不足"

        weekly_comparison[nkey] = {
            "avg": avg_val,
            "unit": unit,
            "dri": dri,
            "pct": pct,
            "status": status,
        }

    # 趋势分析
    trends = []
    if daily_sodium:
        max_na = max(daily_sodium)
        avg_na = sum(daily_sodium) / len(daily_sodium)
        na_pi = get_dri_value("na", gender) or 2000
        if avg_na > na_pi:
            trends.append(f"日均钠摄入 {avg_na:.0f}mg，超过建议摄入量 {na_pi}mg，需减盐")
        if max_na > na_pi * 1.5:
            trends.append(f"最高单日钠 {max_na}mg，超标严重")

    if daily_kcal:
        avg_kcal = sum(daily_kcal) / len(daily_kcal)
        dri_kcal = get_dri_value("kcal", gender)
        if avg_kcal < dri_kcal * 0.7:
            trends.append(f"日均能量 {avg_kcal:.0f}kcal，仅为参考值的{avg_kcal/dri_kcal*100:.0f}%，可能能量不足")
        elif avg_kcal > dri_kcal * 1.2:
            trends.append(f"日均能量 {avg_kcal:.0f}kcal，超过参考值20%，注意控制")

    if daily_protein:
        avg_protein = sum(daily_protein) / len(daily_protein)
        dri_protein = get_dri_value("protein", gender)
        if avg_protein < dri_protein * 0.7:
            trends.append(f"日均蛋白质 {avg_protein:.0f}g，低于参考值30%，需增加优质蛋白")

    # 蔬菜不足
    if no_veg_days > 0:
        trends.append(f"有{no_veg_days}天无蔬菜类菜品，需增加蔬菜摄入")

    # 食物多样性
    trends.append(f"本周涉及{len(categories_all)}个菜品大类: {'、'.join(categories_all)}")

    # 健康建议
    suggestions = []
    for nkey, info in weekly_comparison.items():
        if info["status"] in ["不足", "偏低"]:
            label = NUTRIENT_LABELS.get(nkey, (nkey, ""))[0]
            suggestions.append(f"增加{label}摄入: 日均{info['avg']}{info['unit']}，参考值{info['dri']}{info['unit']}")
        elif info["status"] in ["超标", "偏高"]:
            label = NUTRIENT_LABELS.get(nkey, (nkey, ""))[0]
            suggestions.append(f"控制{label}摄入: 日均{info['avg']}{info['unit']}，已超过参考值")

    # 推荐菜品
    recommendations = recommend_dishes(weekly_comparison, gender, limit=10)

    return {
        "days_analyzed": n,
        "daily_summary": daily_results,
        "weekly_avg": avg,
        "weekly_comparison": weekly_comparison,
        "trends": trends,
        "health_suggestions": suggestions,
        "dish_recommendations": recommendations,
        "categories_covered": list(categories_all),
    }


# ============================================================
# 模式4: 菜品推荐引擎
# ============================================================

def recommend_dishes(comparison, gender="male", limit=8):
    """根据营养缺口推荐菜品"""
    db = load_db()

    # 找出不足的营养素
    deficient = []
    excessive = []
    for nkey, info in comparison.items():
        status = info.get("status", "")
        if isinstance(info, dict) and "pct" in info:
            pct = info["pct"]
        else:
            pct = info.get("daily_pct", 0)
            status = info.get("grade", "")

        if status in ["不足", "偏低", "缺失"]:
            deficient.append(nkey)
        elif status in ["超标", "偏高", "过高"]:
            excessive.append(nkey)

    # 钠超标时不推荐高钠菜
    avoid_high_na = "na" in excessive

    # 评分推荐
    scored = []
    for d in db:
        score = 0
        reasons = []

        # 补充不足营养素
        for nkey in deficient:
            val = d.get(nkey, 0)
            if val > 0:
                dri = get_dri_value(nkey, gender)
                if dri and dri > 0:
                    contribution = val / dri * 100
                    if contribution > 10:
                        score += contribution * 0.5
                        if contribution > 20:
                            reasons.append(f"富含{NUTRIENT_LABELS.get(nkey, (nkey, ''))[0]}")

        # 避免过量营养素
        for nkey in excessive:
            val = d.get(nkey, 0)
            dri = get_dri_value(nkey, gender)
            if dri and dri > 0:
                ratio = val / dri * 100
                if ratio > 30:
                    score -= ratio * 0.8
                    reasons.append(f"{NUTRIENT_LABELS.get(nkey, (nkey, ''))[0]}较高")

        # 钠控制
        if avoid_high_na and d.get("na", 0) > 600:
            score -= 20

        # 营养等级加分
        if d.get("grade") == "优":
            score += 15
        elif d.get("grade") == "良":
            score += 8

        # 蔬菜类额外加分（补充膳食纤维和维生素）
        if d["category"] == "蔬菜菌菇类":
            score += 5
        if d["category"] == "豆制品类":
            score += 5

        if score > 5:
            scored.append((d, score, reasons))

    scored.sort(key=lambda x: -x[1])

    results = []
    seen_categories = set()
    for d, score, reasons in scored[:limit * 2]:
        if d["category"] in seen_categories and len(results) >= 3:
            continue
        seen_categories.add(d["category"])
        results.append({
            "name": d["name"],
            "category": d["category"],
            "kcal": d["kcal"],
            "protein": d["protein"],
            "fat": d["fat"],
            "na": d["na"],
            "grade": d["grade"],
            "reason": "；".join(reasons) if reasons else "综合营养评分高",
            "ingredients": d.get("ingredients", ""),
        })
        if len(results) >= limit:
            break

    return results


def mode_recommend(gaps_input, gender="male", limit=10):
    """基于营养缺口推荐菜品
    gaps_input: list of nutrient keys that are deficient
    """
    db = load_db()
    ref = get_reference(gender)

    scored = []
    for d in db:
        score = 0
        reasons = []

        for nkey in gaps_input:
            val = d.get(nkey, 0)
            dri = get_dri_value(nkey, gender)
            if dri and dri > 0:
                contribution = val / dri * 100
                if contribution > 10:
                    score += contribution
                    if contribution > 20:
                        label = NUTRIENT_LABELS.get(nkey, (nkey, ""))[0]
                        reasons.append(f"富含{label}({val}{NUTRIENT_LABELS.get(nkey, (nkey, ''))[1]})")

        # 钠低优先
        if d.get("na", 0) < 400:
            score += 10

        if d.get("grade") == "优":
            score += 15
        elif d.get("grade") == "良":
            score += 8

        if score > 5:
            scored.append((d, score, reasons))

    scored.sort(key=lambda x: -x[1])

    results = []
    seen = set()
    for d, score, reasons in scored[:limit * 3]:
        if d["category"] in seen and len(results) >= 4:
            continue
        seen.add(d["category"])
        results.append({
            "name": d["name"],
            "category": d["category"],
            "kcal": d["kcal"],
            "protein": d["protein"],
            "fat": d["fat"],
            "na": d["na"],
            "grade": d["grade"],
            "reason": "；".join(reasons) if reasons else "综合营养评分高",
            "ingredients": d.get("ingredients", ""),
        })
        if len(results) >= limit:
            break

    return results


# ============================================================
# 模式5: 搜索
# ============================================================

def mode_search(keyword, limit=20):
    """按关键词搜索菜品"""
    db = load_db()
    results = []
    for d in db:
        if keyword in d["name"] or keyword in d.get("ingredients", ""):
            results.append({
                "idx": d["idx"],
                "name": d["name"],
                "category": d["category"],
                "kcal": d["kcal"],
                "protein": d["protein"],
                "grade": d["grade"],
                "ingredients": d.get("ingredients", ""),
            })
    return results[:limit]


# ============================================================
# 模式6: 分类列表
# ============================================================

def mode_category(cat_name):
    """按分类列出菜品"""
    db = load_db()
    # 模糊匹配分类名
    cat_map = {
        "猪肉": "猪牛羊肉类", "牛肉": "猪牛羊肉类", "羊肉": "猪牛羊肉类",
        "鸡肉": "鸡鸭禽肉类", "鸭肉": "鸡鸭禽肉类", "禽肉": "鸡鸭禽肉类",
        "鱼": "鱼虾海鲜类", "虾": "鱼虾海鲜类", "海鲜": "鱼虾海鲜类",
        "蛋": "蛋类", "鸡蛋": "蛋类",
        "蔬菜": "蔬菜菌菇类", "菌菇": "蔬菜菌菇类", "素菜": "蔬菜菌菇类",
        "豆制品": "豆制品类", "豆腐": "豆制品类",
        "汤": "汤粥类", "粥": "汤粥类",
        "主食": "主食类", "面食": "主食类",
        "凉菜": "凉菜类", "水果": "水果类",
    }
    target = None
    for k, v in cat_map.items():
        if k in cat_name:
            target = v
            break
    if not target:
        for c in set(d["category"] for d in db):
            if cat_name in c:
                target = c
                break

    if not target:
        return {"error": f"未找到分类: {cat_name}",
                "available": list(set(d["category"] for d in db))}

    dishes = [d for d in db if d["category"] == target]
    return {
        "category": target,
        "count": len(dishes),
        "dishes": [{"idx": d["idx"], "name": d["name"], "kcal": d["kcal"],
                     "protein": d["protein"], "grade": d["grade"]}
                   for d in dishes]
    }


# ============================================================
# 模式7: 一餐营养报告
# ============================================================

def mode_menu(dishes_input, gender="male", meal_type="lunch"):
    """生成一餐营养报告，含缺口分析和搭配建议"""
    daily_result = mode_daily(dishes_input, gender)
    if "error" in daily_result:
        return daily_result

    # 一餐参考量（按午餐40%计）
    ref = get_reference(gender)
    meal_ratio = {"breakfast": 0.3, "lunch": 0.4, "dinner": 0.35}.get(meal_type, 0.35)
    dri_kcal = get_dri_value("kcal", gender)
    meal_target_kcal = round(dri_kcal * meal_ratio)

    totals = daily_result["totals"]

    # 一餐营养评估
    meal_assessment = {}
    for nkey in ["kcal", "protein", "fat", "na", "ca", "fe", "vc"]:
        val = totals.get(nkey, 0)
        dri_daily = get_dri_value(nkey, gender)
        meal_target = round(dri_daily * meal_ratio) if dri_daily else 0
        pct = round(val / meal_target * 100, 1) if meal_target else 0

        if nkey == "na":
            if pct > 120:
                status = "超标"
            elif pct > 80:
                status = "偏高"
            else:
                status = "适宜"
        elif nkey == "fat":
            if pct > 120:
                status = "超标"
            elif pct > 90:
                status = "偏高"
            elif pct > 0:
                status = "适宜"
            else:
                status = "不足"
        elif nkey in ["kcal", "protein"]:
            if pct >= 90:
                status = "达标"
            elif pct >= 70:
                status = "偏低"
            else:
                status = "不足"
        else:
            if pct >= 80:
                status = "达标"
            elif pct >= 50:
                status = "偏低"
            else:
                status = "不足"

        meal_assessment[nkey] = {
            "value": val,
            "target": meal_target,
            "pct": pct,
            "status": status,
        }

    # 搭配建议
    pairing_suggestions = []
    gaps = [k for k, v in meal_assessment.items() if v["status"] in ["不足", "偏低"]]
    if gaps:
        recs = recommend_dishes(
            {k: {"status": v["status"], "pct": v["pct"]} for k, v in meal_assessment.items()},
            gender, limit=5
        )
        for r in recs:
            pairing_suggestions.append({
                "name": r["name"],
                "category": r["category"],
                "kcal": r["kcal"],
                "reason": r.get("reason", ""),
            })

    return {
        "meal_type": meal_type,
        "meal_target_kcal": meal_target_kcal,
        "dishes": daily_result["matched_dishes"],
        "not_found": daily_result["not_found"],
        "totals": totals,
        "meal_assessment": meal_assessment,
        "food_diversity": daily_result["food_diversity"],
        "gaps": gaps,
        "pairing_suggestions": pairing_suggestions,
        "sodium_warning": daily_result.get("totals", {}).get("na", 0) > 670,
    }


# ============================================================
# 主入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python nutrition_analysis.py <mode> [args]")
        print("模式: single <菜名> [gender] [meal]")
        print("      daily <菜名1,菜名2,...> [gender]")
        print("      weekly <json_file> [gender]")
        print("      recommend <nutrient1,nutrient2,...> [gender] [limit]")
        print("      search <关键词>")
        print("      category <分类名>")
        print("      menu <菜名1,菜名2,...> [gender] [meal]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "single":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要菜名参数"}))
            sys.exit(1)
        dish_name = sys.argv[2]
        gender = sys.argv[3] if len(sys.argv) > 3 else "male"
        meal = sys.argv[4] if len(sys.argv) > 4 else "lunch"
        result = mode_single(dish_name, gender, meal)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "daily":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要菜品列表参数（逗号分隔）"}))
            sys.exit(1)
        dishes = [d.strip() for d in sys.argv[2].split(",")]
        gender = sys.argv[3] if len(sys.argv) > 3 else "male"
        result = mode_daily(dishes, gender)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "weekly":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要JSON文件路径"}))
            sys.exit(1)
        json_file = sys.argv[2]
        gender = sys.argv[3] if len(sys.argv) > 3 else "male"
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "gender" not in data:
            data["gender"] = gender
        result = mode_weekly(data, data.get("gender", gender))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "recommend":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要营养素列表（逗号分隔）"}))
            sys.exit(1)
        gaps = [g.strip() for g in sys.argv[2].split(",")]
        gender = sys.argv[3] if len(sys.argv) > 3 else "male"
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        result = mode_recommend(gaps, gender, limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "search":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要搜索关键词"}))
            sys.exit(1)
        keyword = sys.argv[2]
        result = mode_search(keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "category":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要分类名"}))
            sys.exit(1)
        cat = sys.argv[2]
        result = mode_category(cat)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "menu":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "需要菜品列表（逗号分隔）"}))
            sys.exit(1)
        dishes = [d.strip() for d in sys.argv[2].split(",")]
        gender = sys.argv[3] if len(sys.argv) > 3 else "male"
        meal = sys.argv[4] if len(sys.argv) > 4 else "lunch"
        result = mode_menu(dishes, gender, meal)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(json.dumps({"error": f"未知模式: {mode}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
