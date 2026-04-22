# 如何使用 law-v2.0-20260413.yaml 配置文件

**配置文件路径**：`configs/frameworks/law-v2.0-20260413.yaml`  
**版本**：v2.0.0  
**创建日期**：2026-04-13  
**适用场景**：法学论文 AI 辅助评价

---

## 一、配置文件结构概览

```yaml
metadata:           # 元数据（版本、学科、来源）
precheck:           # 准入条件（前置筛选）
scoring_structure:  # 评分结构（总分 100）
dimensions:         # 六维度定义
evaluation_chain:   # 判断链条顺序
discrimination_threshold:  # 区分度阈值
expert_review_triggers:    # 专家复核触发条件
anchors:            # 样本锚点（正负样本）
```

---

## 二、使用流程

### 步骤 1：加载配置文件

```python
import yaml

# 加载配置
with open('configs/frameworks/law-v2.0-20260413.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 获取元数据
metadata = config['metadata']
print(f"框架名称: {metadata['name']}")
print(f"版本: {metadata['version']}")
print(f"学科: {metadata['discipline']}")
```

### 步骤 2：执行准入条件检查

```python
# 获取准入条件配置
precheck = config['precheck']
prompt_template = precheck['prompt_template']

# 构建 AI 请求
def check_precheck(paper_text):
    """
    执行学术规范性准入检查
    
    Args:
        paper_text: 论文全文
        
    Returns:
        dict: {"status": "pass|reject", "issues": [...], "recommendation": "..."}
    """
    prompt = prompt_template.replace("{论文全文}", paper_text)
    
    # 调用 AI 模型
    response = ai_model.generate(prompt)
    result = json.loads(response)
    
    return result

# 使用示例
precheck_result = check_precheck(paper_text)

if precheck_result['status'] == 'reject':
    print("论文未通过准入检查，建议退稿")
    print(f"问题：{precheck_result['issues']}")
    return  # 不进入六维评分
else:
    print("论文通过准入检查，进入六维评分")
```

### 步骤 3：六维度评分

```python
# 获取维度配置
dimensions = config['dimensions']

# 遍历六个维度
dimension_scores = {}

for dim in dimensions:
    key = dim['key']
    name_zh = dim['name_zh']
    weight = dim['weight']
    prompt_template = dim['prompt_template']
    
    # 构建 AI 请求
    prompt = prompt_template  # 可以插入论文文本
    
    # 调用 AI 模型
    response = ai_model.generate(prompt)
    result = json.loads(response)
    
    # 保存结果
    dimension_scores[key] = {
        'name': name_zh,
        'score': result['score'],  # 0-100
        'weight': weight,
        'evidence': result['evidence_quotes'],
        'analysis': result['analysis']
    }
    
    print(f"{name_zh}: {result['score']}分 (权重{weight*100}%)")

# 计算总分
total_score = sum(
    dim_score['score'] * dim_score['weight'] 
    for dim_score in dimension_scores.values()
)
print(f"\n总分: {total_score:.2f}/100")
```

### 步骤 4：判断是否需要专家复核

```python
# 获取专家复核触发条件
expert_triggers = config['expert_review_triggers']

# 检查维度触发条件
needs_expert_review = False

for trigger in expert_triggers['dimension_triggers']:
    dim_key = trigger['dimension']
    condition = trigger['condition']
    
    # 示例：问题创新性 < 40 分
    if dim_key == 'problem_originality':
        if dimension_scores[dim_key]['score'] < 40:
            needs_expert_review = True
            print(f"触发专家复核：{condition}")

# 检查整体触发条件
# 示例：多模型评分标准差 > 5
if std_deviation > 5:
    needs_expert_review = True
    print("触发专家复核：多模型分歧大")

if needs_expert_review:
    print("\n需要专家复核")
else:
    print("\n高置信度，可直接使用 AI 评分")
```

---

## 三、关键字段说明

### 3.1 准入条件 (precheck)

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 准入检查名称 |
| `description` | string | 检查说明 |
| `criteria` | list | 检查项列表 |
| `criteria[].key` | string | 检查项标识符 |
| `criteria[].name_zh` | string | 检查项中文名 |
| `criteria[].description` | string | 检查项描述 |
| `criteria[].pass_required` | boolean | 是否必须通过 |
| `prompt_template` | string | AI 评价 prompt |

**输出格式**：
```json
{
  "status": "pass|reject",
  "issues": ["问题1", "问题2"],
  "recommendation": "处理建议"
}
```

### 3.2 维度定义 (dimensions)

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | string | 维度标识符（如 `problem_originality`） |
| `name_zh` | string | 维度中文名 |
| `name_en` | string | 维度英文名 |
| `weight` | float | 权重（0-1，总和为 1.0） |
| `position` | int | 判断链条中的位置 |
| `position_name` | string | 位置名称（如"起点"） |
| `ai_difficulty` | string | AI 评价难度（high/medium/low） |
| `needs_expert_review` | boolean | 是否需要专家复核 |
| `description` | string | 维度描述 |
| `scoring_criteria` | object | 评分标准（excellent/good/marginal/unacceptable） |
| `positive_anchor` | object | 正样本锚点 |
| `negative_anchor` | object | 负样本锚点 |
| `prompt_template` | string | AI 评价 prompt |

**输出格式**：
```json
{
  "dimension": "problem_originality",
  "score": 85,
  "evidence_quotes": ["引用1", "引用2"],
  "analysis": "分析说明"
}
```

---

## 四、评分计算公式

### 总分计算

```python
total_score = (
    problem_originality_score * 0.30 +      # 问题创新性 30%
    literature_insight_score * 0.15 +       # 现状洞察度 15%
    analytical_framework_score * 0.15 +     # 分析框架建构力 15%
    logical_coherence_score * 0.25 +        # 逻辑严密性 25%
    conclusion_consensus_score * 0.10 +     # 结论共识度 10%
    forward_extension_score * 0.05          # 前瞻延展性 5%
)
```

### 可靠性判断

```python
# 多模型并发评价
scores = [model1_score, model2_score, model3_score]
mean_score = np.mean(scores)
std_deviation = np.std(scores)

# 置信度判断
if std_deviation <= 5:
    confidence = "high"  # 高置信度
else:
    confidence = "low"   # 低置信度，需专家复核
```

---

## 五、完整示例代码

```python
import yaml
import json
import numpy as np

class LawEvaluationV2:
    def __init__(self, config_path='configs/frameworks/law-v2.0-20260413.yaml'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    def evaluate(self, paper_text, ai_models):
        """
        完整评价流程
        
        Args:
            paper_text: 论文全文
            ai_models: AI 模型列表（多模型并发）
            
        Returns:
            dict: 评价结果
        """
        # 步骤 1：准入检查
        precheck_result = self.check_precheck(paper_text, ai_models[0])
        if precheck_result['status'] == 'reject':
            return {
                'status': 'rejected',
                'reason': 'precheck_failed',
                'issues': precheck_result['issues']
            }
        
        # 步骤 2：多模型并发评价
        all_scores = []
        for model in ai_models:
            scores = self.evaluate_dimensions(paper_text, model)
            all_scores.append(scores)
        
        # 步骤 3：计算均值和标准差
        dimension_results = {}
        for dim_key in all_scores[0].keys():
            scores = [s[dim_key]['score'] for s in all_scores]
            dimension_results[dim_key] = {
                'mean': np.mean(scores),
                'std': np.std(scores),
                'scores': scores
            }
        
        # 步骤 4：计算总分
        total_score = self.calculate_total_score(dimension_results)
        
        # 步骤 5：判断置信度
        max_std = max(d['std'] for d in dimension_results.values())
        confidence = 'high' if max_std <= 5 else 'low'
        
        # 步骤 6：判断是否需要专家复核
        needs_expert = self.check_expert_review(dimension_results, confidence)
        
        return {
            'status': 'evaluated',
            'total_score': total_score,
            'confidence': confidence,
            'needs_expert_review': needs_expert,
            'dimensions': dimension_results
        }
    
    def check_precheck(self, paper_text, model):
        """执行准入检查"""
        prompt = self.config['precheck']['prompt_template']
        response = model.generate(prompt.format(paper_text=paper_text))
        return json.loads(response)
    
    def evaluate_dimensions(self, paper_text, model):
        """评价六个维度"""
        results = {}
        for dim in self.config['dimensions']:
            prompt = dim['prompt_template']
            response = model.generate(prompt.format(paper_text=paper_text))
            result = json.loads(response)
            results[dim['key']] = result
        return results
    
    def calculate_total_score(self, dimension_results):
        """计算总分"""
        total = 0
        for dim in self.config['dimensions']:
            key = dim['key']
            weight = dim['weight']
            mean_score = dimension_results[key]['mean']
            total += mean_score * weight
        return total
    
    def check_expert_review(self, dimension_results, confidence):
        """判断是否需要专家复核"""
        if confidence == 'low':
            return True
        
        # 检查维度触发条件
        for trigger in self.config['expert_review_triggers']['dimension_triggers']:
            dim_key = trigger['dimension']
            condition = trigger['condition']
            
            # 解析条件（简化示例）
            if '<40' in condition:
                if dimension_results[dim_key]['mean'] < 40:
                    return True
            elif '<50' in condition:
                if dimension_results[dim_key]['mean'] < 50:
                    return True
        
        return False

# 使用示例
evaluator = LawEvaluationV2()
result = evaluator.evaluate(paper_text, [model1, model2, model3])

print(f"评价状态: {result['status']}")
print(f"总分: {result['total_score']:.2f}/100")
print(f"置信度: {result['confidence']}")
print(f"需要专家复核: {result['needs_expert_review']}")
```

---

## 六、注意事项

### 6.1 准入条件是前置筛选
- 不合格论文直接退稿，不进入六维评分
- 节省 AI 和专家资源

### 6.2 判断链条顺序不可颠倒
- 起点（问题创新性）→ 定位（现状洞察度）→ 工具（分析框架建构力）→ 骨架（逻辑严密性）→ 落脚（结论共识度）→ 开放（前瞻延展性）
- 前一步失败会影响后续评价

### 6.3 前瞻延展性权重最低
- 权重仅 5%，对判例分析类论文影响小
- 即使得 50 分，对总分影响仅 2.5 分

### 6.4 多模型并发验证
- 建议使用 3-5 个模型并发评价
- 标准差 ≤ 5 分为高置信度

### 6.5 专家复核触发条件
- 问题创新性 < 40 分
- 结论共识度 < 50 分
- 多模型分歧大（标准差 > 5）

---

## 七、与 v1.0 的差异

| 项目 | v1.0 | v2.0 |
|------|------|------|
| 准入条件 | 无 | 有（学术规范性） |
| 核心维度数 | 6 | 6 |
| 总分范围 | 0-100 | 0-100 |
| 问题创新性权重 | 25% | 30% |
| 逻辑严密性权重 | 20% | 25% |
| 结论共识度权重 | 15% | 10% |
| 前瞻延展性权重 | 10% | 5% |

---

## 八、相关文档

- **评分细则**：`docs/evaluation/law-scoring-rules-v0.1-20260413.md`
- **架构决策**：`docs/architecture/20260414_ADR-001_evaluation-framework-v2.md`
- **v1.0 归档**：`configs/frameworks/archive/law-v1.0-20260413.yaml`
- **项目上下文**：`CLAUDE.md`
