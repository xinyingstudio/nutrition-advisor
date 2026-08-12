# nutrition-advisor · 高校食堂菜品营养顾问

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个面向高职院校学生食堂点餐场景的菜品营养分析与健康膳食推荐工具。

基于 1152 道食堂菜品的标准营养数据库，对照《中国居民膳食营养素参考摄入量 DRIs（2023）》《中国居民膳食指南（2022）》《WS/T 554-2017 学生餐营养指南》等权威标准，帮助学生了解「吃了什么、获得了什么营养、还缺什么、该怎么搭」。

> 也可作为 [WorkBuddy](https://www.workbuddy.cn) 的 Skill 使用（见文末「作为 WorkBuddy 技能使用」）。

## ✨ 功能特性

- **单菜营养查询**：输入菜名，输出 18 项营养指标 + 占日参考量百分比 + 营养等级 + 钠警示 + 过敏原 + 膳食建议
- **一餐营养报告**：多菜组合，按早/午/晚餐目标量评估，识别能量/钠缺口并给出搭配建议
- **单日营养汇总**：全天摄入 vs DRIs 对比 + 食物多样性评估
- **一周综合分析**：趋势识别 + 个性化健康建议 + 10 道推荐菜
- **智能菜品推荐**：基于营养缺口从 1152 道库中按评分筛选
- **分类浏览 / 关键词搜索**：快速定位菜品
- **男/女差异**：女性铁需求比男性高 50%（18 vs 12 mg/d），分性别设定参考值

## 📁 目录结构

```
nutrition-advisor/
├── SKILL.md                        # 技能指令（WorkBuddy 兼容）
├── README.md                       # 本文件
├── LICENSE                         # MIT
├── .gitignore
├── scripts/
│   └── nutrition_analysis.py       # 分析引擎（7 种模式）
├── data/
│   └── dishes_nutrition.json       # 1152 道菜品营养数据（示例数据集）
└── references/
    ├── dris_2023.json              # DRIs 2023 参考值 + WS/T 554-2017 学生餐标准
    └── dietary_guidelines_2022.md  # 膳食指南 2022 八大准则 + 大学生特别提示
```

## 🚀 安装

要求 **Python 3.8+**，仅依赖标准库，无需 `pip install`。

```bash
git clone https://github.com/<your-username>/nutrition-advisor.git
cd nutrition-advisor
python scripts/nutrition_analysis.py --help
```

## 📖 使用

脚本通过 `__file__` 自动定位 `data/` 与 `references/`，无需写死绝对路径。

```bash
# 进入技能根目录
cd path/to/nutrition-advisor

# 1) 单道菜品营养查询
python scripts/nutrition_analysis.py single "鱼香肉丝" male lunch
#    参数: 菜名 性别(male/female) 餐次(breakfast/lunch/dinner)

# 2) 单日营养汇总
python scripts/nutrition_analysis.py daily "鱼香肉丝,番茄炒蛋,清炒西兰花" male
#    参数: 逗号分隔菜名 性别

# 3) 一周营养综合分析（传入 JSON 文件）
python scripts/nutrition_analysis.py weekly /path/to/weekly_data.json male
#    JSON 格式见下

# 4) 基于营养缺口推荐菜品
python scripts/nutrition_analysis.py recommend "protein,fiber,ca,vc" male 8
#    参数: 逗号分隔营养素key 性别 推荐数量

# 5) 搜索菜品
python scripts/nutrition_analysis.py search "鸡蛋"

# 6) 按分类列出菜品
python scripts/nutrition_analysis.py category "蔬菜"

# 7) 一餐营养报告（含搭配建议）
python scripts/nutrition_analysis.py menu "鱼香肉丝,番茄炒蛋" male lunch
```

### 周分析 JSON 输入格式

```json
{
  "gender": "male",
  "days": [
    {"date": "2026-08-05", "dishes": ["鱼香肉丝", "番茄炒蛋", "白菜炖豆腐"]},
    {"date": "2026-08-06", "dishes": ["红烧排骨", "清炒西兰花", "蒸鸡蛋羹"]}
  ]
}
```

### 营养素 key 对照表

| key | 中文名 | 单位 | 日参考（男/女） |
|-----|--------|------|----------------|
| kcal | 能量 | kcal | 2400 / 2000 |
| protein | 蛋白质 | g | 65 / 55 |
| fat | 脂肪 | g | AMDR 20–30%E |
| carb | 碳水化合物 | g | AMDR 50–65%E |
| fiber | 膳食纤维 | g | 30 / 25 |
| na | 钠 | mg | PI 2000 |
| ca | 钙 | mg | RNI 800 |
| fe | 铁 | mg | 12 / 18 |
| zn | 锌 | mg | 12.5 / 7.5 |
| va | 维生素A | μgRAE | 800 / 700 |
| vc | 维生素C | mg | RNI 100 |
| chol | 胆固醇 | mg | PI < 300 |

## 📊 数据说明

`data/dishes_nutrition.json` 为**示例数据集**，来源于青岛酒店管理职业技术学院后勤「青酒管微后勤」2025–2026 学年食堂菜品（1152 道，已去重）。所有营养值依据《中国食物成分表》第 6 版，按**生重、可食部**测算，不同烹饪方式已估算添加油盐。

如需用于其他学校 / 食堂，可替换该 JSON 文件，保持字段结构一致即可：

```json
{
  "idx": 1,
  "name": "菜名",
  "category": "分类",
  "cooking": "烹饪方式",
  "ingredients": "食材(生重·可食部)",
  "weight": 每份克数,
  "kcal": 能量, "protein": 蛋白质, "fat": 脂肪, "carb": 碳水,
  "fiber": 膳食纤维, "na": 钠, "ca": 钙, "fe": 铁, "zn": 锌,
  "va": 维生素A, "vc": 维生素C, "chol": 胆固醇,
  "grade": "优/良/一般/限制",
  "allergens": "过敏原", "advice": "膳食建议"
}
```

## 📐 标准依据

- WS/T 554-2017《学生餐营养指南》（中小学强制执行，高校食堂参照）
- 《学校食品安全与营养健康管理规定》教育部 45 号令（食堂公示、食谱审核硬性要求）
- 《中国食物成分表》第 6 版（食材营养测算权威数据库）
- 《中国居民膳食指南（2022）》
- 《中国居民膳食营养素参考摄入量 DRIs（2023）》

## ⚠️ 免责声明

本工具营养数据为**估算值**，基于菜名推断食材 + 标准食物成分表计算，实际烹饪存在偏差，仅供参考，不构成医疗或营养诊疗建议。

## 🧩 作为 WorkBuddy 技能使用

将本仓库放入 WorkBuddy 的技能目录即可被自动识别：

- 用户级：`~/.workbuddy/skills/nutrition-advisor/`
- 项目级：`<项目>/.workbuddy/skills/nutrition-advisor/`

对话中出现「菜品营养、营养分析、点餐营养、外卖营养、膳食建议、营养缺口」等关键词时会自动触发。

## 📄 许可证

[MIT](LICENSE) © 2026 青酒管微后勤 / Xinying
