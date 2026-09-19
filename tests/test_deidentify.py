"""去識別化測試。每一條都測「該遮」與「不該遮」兩個方向。

隱私類的測試偏向嚴格：漏遮是紅線，誤遮只是精確度損失。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deidentify import audit, deidentify, load_whitelist

WL = load_whitelist(Path(__file__).resolve().parents[1] / "data" / "public_figures.json")


class TestMustRedact:
    def test_連結(self):
        out, log = deidentify("看這個 https://fb.com/posts/123 就懂了", WL)
        assert "fb.com" not in out and "[連結]" in out
        assert log[0]["kind"] == "url"

    def test_at提及(self):
        out, _ = deidentify("@王小明 你看看這個判罰", WL)
        assert "王小明" not in out and "[提及]" in out

    def test_全形at提及(self):
        out, _ = deidentify("＠小華 快來", WL)
        assert "小華" not in out

    def test_信箱(self):
        out, _ = deidentify("寄到 abc.def@gmail.com 給我", WL)
        assert "gmail" not in out and "[信箱]" in out

    def test_手機號碼(self):
        out, _ = deidentify("我的電話 0912-345-678", WL)
        assert "0912" not in out and "[號碼]" in out

    def test_正文裡的人名(self):
        out, log = deidentify("陳建宏說這個策略有問題", WL)
        assert "陳建宏" not in out
        assert any(i["kind"] == "name" for i in log)

    def test_信箱不會被at規則切一半(self):
        out, _ = deidentify("聯絡 user@mail.com 謝謝", WL)
        assert "mail.com" not in out
        assert out.count("[信箱]") == 1


class TestMustKeep:
    def test_車手英文名保留(self):
        out, _ = deidentify("Verstappen 這個超車太扯了", WL)
        assert "Verstappen" in out

    def test_車隊名保留(self):
        out, _ = deidentify("紅牛的策略又出問題", WL)
        assert "紅牛" in out

    def test_普通詞不被當人名(self):
        for word in ("馬上", "高速", "白色", "石頭", "方向", "黃牌", "紅牌"):
            out, log = deidentify(f"這個{word}很關鍵", WL)
            assert word in out, f"{word} 被誤遮了"
            assert not any(i["kind"] == "name" for i in log), f"{word} 被當人名"

    def test_純賽事討論零遮蔽(self):
        out, log = deidentify("這場的輪胎策略很關鍵，安全車出來之後名次全亂了", WL)
        assert log == []
        assert out == "這場的輪胎策略很關鍵，安全車出來之後名次全亂了"


class TestAudit:
    def test_批次統計(self):
        rows = [
            "@小明 看這個 https://x.com/a",
            "Verstappen 太強了",
            "李大同 說得對",
        ]
        cleaned, counts = audit(rows, WL)
        assert len(cleaned) == 3
        assert counts.get("mention") == 1
        assert counts.get("url") == 1
        assert counts.get("name") == 1
        assert "Verstappen" in cleaned[1]

    def test_遮蔽紀錄不會出現在清理後文字裡(self):
        out, log = deidentify("@某人 我的信箱 a@b.com", WL)
        for item in log:
            assert item["original"] not in out
