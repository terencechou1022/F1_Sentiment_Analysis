"""指標測試。重點在驗證「逐類報告會揭露 macro 藏起來的弱類別」。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metrics import LABELS_SENTIMENT, format_report, per_class, report


class TestPerClass:
    def test_全對時三類都是一(self):
        y = ["positive", "negative", "neutral"]
        got = per_class(y, y, LABELS_SENTIMENT)
        for label in LABELS_SENTIMENT:
            assert got[label]["f1"] == 1.0
            assert got[label]["support"] == 1

    def test_全錯時三類都是零(self):
        got = per_class(["positive"] * 3, ["negative"] * 3, LABELS_SENTIMENT)
        assert got["positive"]["f1"] == 0.0
        assert got["negative"]["f1"] == 0.0

    def test_support是真實標籤數不是預測數(self):
        got = per_class(
            ["neutral"] * 5, ["positive"] * 5, LABELS_SENTIMENT
        )
        assert got["neutral"]["support"] == 5
        assert got["positive"]["support"] == 0


class TestReport:
    def test_macro只算有樣本的類別(self):
        # 只有兩類出現，macro 不該被不存在的第三類的 0 拉低
        y_true = ["positive", "negative"]
        got = report(y_true, y_true, LABELS_SENTIMENT)
        assert got["macro_f1"] == 1.0

    def test_中立類低分會被指名(self):
        # 正負各 4 筆全對，中立 4 筆全錯：這正是 macro 會藏起來的情況
        y_true = ["positive"] * 4 + ["negative"] * 4 + ["neutral"] * 4
        y_pred = ["positive"] * 4 + ["negative"] * 4 + ["positive"] * 4
        got = report(y_true, y_pred, LABELS_SENTIMENT)
        assert got["weakest_class"] == "neutral"
        assert got["weakest_f1"] == 0.0
        # 正負看起來很漂亮
        assert got["per_class"]["negative"]["f1"] == 1.0
        # 但 macro 已經被拉下來，而逐類報告讓原因看得見
        assert got["macro_f1"] < 0.75

    def test_accuracy與macro會分歧(self):
        # 類別不平衡時 accuracy 高但 macro 低，這是要在報告裡講的
        y_true = ["positive"] * 18 + ["neutral"] * 2
        y_pred = ["positive"] * 20
        got = report(y_true, y_pred, LABELS_SENTIMENT)
        assert got["accuracy"] == 0.9
        assert got["macro_f1"] < 0.6

    def test_空輸入不炸(self):
        got = report([], [], LABELS_SENTIMENT)
        assert got["n"] == 0
        assert got["macro_f1"] == 0.0
        assert got["weakest_class"] is None


class TestFormat:
    def test_表格含三類與弱類別提示(self):
        y_true = ["positive"] * 3 + ["neutral"] * 3
        y_pred = ["positive"] * 3 + ["positive"] * 3
        text = format_report(report(y_true, y_pred, LABELS_SENTIMENT))
        assert "macro F1" in text
        assert "neutral" in text
        assert "最弱類別" in text

    def test_空輸入的表格不含弱類別提示(self):
        text = format_report(report([], [], LABELS_SENTIMENT))
        assert "最弱類別" not in text
