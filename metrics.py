"""分類指標。每一類都報 P／R／F1，不只報 macro 平均。

驗收標準改成逐類報告是刻意的。三分類的中立類別是 macro-F1 的殺手：
正負好分、中立難分，macro-F1 0.75 很可能是「正負各 0.85、中立 0.55」的平均。
只報 macro 會把這件事藏起來，而它正是報告裡最該討論的部分。

不用 sklearn，因為只需要混淆矩陣與三個比值，自己算 40 行，
少一個相依就少一個版本問題。
"""

LABELS_SENTIMENT = ("positive", "negative", "neutral")
LABELS_TOPIC = (
    "driver_performance",
    "team_strategy",
    "penalty_dispute",
    "race_event",
    "other",
)


def confusion(y_true, y_pred, labels):
    """回傳 {真實標籤: {預測標籤: 次數}}。"""
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix


def per_class(y_true, y_pred, labels):
    """逐類 P／R／F1 與 support。support 要一起看，
    因為小類別的 F1 波動大，光看數字會誤判。"""
    matrix = confusion(y_true, y_pred, labels)
    out = {}
    for label in labels:
        tp = matrix[label][label]
        fn = sum(matrix[label][p] for p in labels if p != label)
        fp = sum(matrix[t][label] for t in labels if t != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
    return out


def report(y_true, y_pred, labels=LABELS_SENTIMENT):
    """逐類指標 + macro／micro 平均 + 最弱的一類。"""
    classes = per_class(y_true, y_pred, labels)
    present = [l for l in labels if classes[l]["support"] > 0]

    macro_f1 = sum(classes[l]["f1"] for l in present) / len(present) if present else 0.0
    correct = sum(t == p for t, p in zip(y_true, y_pred))
    accuracy = correct / len(y_true) if y_true else 0.0

    weakest = min(present, key=lambda l: classes[l]["f1"]) if present else None

    return {
        "per_class": classes,
        "macro_f1": round(macro_f1, 4),
        "accuracy": round(accuracy, 4),
        "n": len(y_true),
        # 最弱的一類要被指名，報告必須解釋它為什麼低
        "weakest_class": weakest,
        "weakest_f1": classes[weakest]["f1"] if weakest else None,
    }


def format_report(result, labels=LABELS_SENTIMENT):
    """給報告直接貼的表格。"""
    lines = [
        f"{'類別':<20}{'P':>8}{'R':>8}{'F1':>8}{'support':>9}",
        "-" * 53,
    ]
    for label in labels:
        row = result["per_class"].get(label)
        if not row:
            continue
        lines.append(
            f"{label:<20}{row['precision']:>8.3f}{row['recall']:>8.3f}"
            f"{row['f1']:>8.3f}{row['support']:>9}"
        )
    lines.append("-" * 53)
    lines.append(f"{'macro F1':<20}{result['macro_f1']:>24.3f}")
    lines.append(f"{'accuracy':<20}{result['accuracy']:>24.3f}")
    lines.append(f"{'n':<20}{result['n']:>24}")
    if result["weakest_class"]:
        lines.append("")
        lines.append(
            f"最弱類別：{result['weakest_class']}（F1 {result['weakest_f1']:.3f}）。"
            "報告必須解釋它為什麼低，見 docs/codebook.md 的中立類別段。"
        )
    return "\n".join(lines)
