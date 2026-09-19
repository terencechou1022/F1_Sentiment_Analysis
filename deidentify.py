"""留言去識別化。隱私紅線：含他人留言的原始資料永遠不進公開 repo。

原 prompt 只寫了移除用戶名稱／ID／連結，那不夠。真正的漏洞在**留言正文**：
「@某某 你看看」的 @提及、正文裡直接寫出的人名、電話、Email，
這些都在 text 欄位裡而不在 metadata 裡。

這支處理的核心難題是**公眾人物與私人要分開**：
分析本身就是關於車手與車隊的討論熱度，所以 Verstappen、Ferrari 必須保留，
但一般網友的名字必須移除。因此採白名單（保留）＋姓氏啟發式（移除）雙軌。

偏誤方向是刻意的：寧可過度遮蔽也不要漏遮。每次遮蔽都記進 audit log，
可以事後人工複核有沒有誤刪車手名。
"""

import json
import re
from pathlib import Path

WHITELIST_PATH = Path("data/public_figures.json")

URL_RE = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|tw|io)\b/?\S*", re.I)
MENTION_RE = re.compile(r"[@＠][\w一-鿿._-]{1,30}")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
# 台灣手機、市話、以及連續 8 碼以上數字（可能是帳號或身分證）
PHONE_RE = re.compile(r"\b09\d{2}[-\s]?\d{3}[-\s]?\d{3}\b|\b0\d{1,2}[-\s]?\d{6,8}\b|\b\d{8,}\b")

# 百家姓。姓氏 + 1 到 2 個漢字視為人名候選。
SURNAMES = (
    "王李張劉陳楊黃趙吳周徐孫馬朱胡郭何高林羅鄭梁謝宋唐許韓馮鄧曹彭曾蕭"
    "田董袁潘蔣蔡余杜葉程蘇魏呂丁任沈姚盧姜崔鍾譚陸汪范金石賈夏韋方白鄒"
    "孟熊秦邱江尹薛閻段雷侯龍史陶黎賀顧毛郝龔邵萬錢嚴武戴莫孔向湯"
)
NAME_RE = re.compile(f"[{SURNAMES}][一-鿿]{{1,2}}")

# 以姓氏字開頭但其實是普通詞，不能當人名遮掉。
# 這份清單是精確度的代價，不完整就會有誤遮，所以 audit log 必須留著。
NOT_NAMES = {
    "馬上", "馬力", "馬赫", "高速", "高溫", "高手", "高層", "高調", "白色", "白癡",
    "石頭", "江湖", "方向", "方式", "方面", "金牌", "金屬", "毛病", "史上", "史詩",
    "龍頭", "夏天", "夏季", "任何", "任務", "程度", "余額", "葉子", "田徑", "董事",
    "汪汪", "孔洞", "向前", "向來", "湯匙", "錢包", "武器", "嚴重", "嚴格", "戴上",
    "范圍", "雷射", "雷同", "段落", "曾經", "曾幾", "黃色", "黃牌", "紅牌",
}

TOKENS = {
    "url": "[連結]",
    "mention": "[提及]",
    "email": "[信箱]",
    "phone": "[號碼]",
    "name": "[人名]",
}


def load_whitelist(path=WHITELIST_PATH):
    """公眾人物白名單。車手與車隊名要保留，否則分析就沒東西可分析。"""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    names = set()
    for group in data.values():
        for entry in group:
            names.add(entry)
    return names


def deidentify(text, whitelist=None):
    """回傳 (清理後文字, 遮蔽紀錄)。紀錄用於人工複核，不進公開 repo。"""
    whitelist = whitelist if whitelist is not None else load_whitelist()
    log = []

    def swap(pattern, kind, s):
        def repl(m):
            log.append({"kind": kind, "original": m.group(0)})
            return TOKENS[kind]
        return pattern.sub(repl, s)

    # 順序有意義。Email 必須排在 URL 之前，否則 URL 規則的網域結尾比對
    # 會把 a@b.com 整段當連結吃掉，信箱就永遠比對不到。
    # @提及排在 Email 之後，否則 @ 會把信箱切一半。
    text = swap(EMAIL_RE, "email", text)
    text = swap(URL_RE, "url", text)
    text = swap(MENTION_RE, "mention", text)
    text = swap(PHONE_RE, "phone", text)

    def name_repl(m):
        token = m.group(0)
        if token in whitelist or token in NOT_NAMES:
            return token
        # NAME_RE 的 {1,2} 是貪婪的，「馬上很關鍵」會抓成「馬上很」，
        # 直接比對整段就對不上 NOT_NAMES。所以要看 2 字前綴。
        if token[:2] in NOT_NAMES or token[:2] in whitelist:
            return token
        log.append({"kind": "name", "original": token})
        return TOKENS["name"]

    text = NAME_RE.sub(name_repl, text)
    return re.sub(r"\s+", " ", text).strip(), log


def audit(rows, whitelist=None):
    """整批處理，回傳清理結果與遮蔽統計，供 P0 驗收的抽樣人工檢查。"""
    whitelist = whitelist if whitelist is not None else load_whitelist()
    cleaned, counts = [], {}
    for row in rows:
        text, log = deidentify(row, whitelist)
        cleaned.append(text)
        for item in log:
            counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return cleaned, counts
