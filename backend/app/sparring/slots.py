from typing import Final

from app.schema import SlotCode

# 埋める順。place を先頭, video を末尾にする根拠は実測(docs/findings.md §4)。残りは答えやすい順
SLOT_ORDER: Final[tuple[SlotCode, ...]] = ("place", "partner", "people", "novelty", "observation", "video")

QUESTIONS: Final[dict[SlotCode, str]] = {
    "place": "どこでやりますか。市区町村まで教えてください。",
    "partner": "社外で関わる相手はいますか。お店, 学校, 自治体, 取引先など。",
    "people": "その日, その場に人はいますか。",
    "novelty": "この取り組みで, 御社として初めてのことはありますか。",
    "observation": "当日, 見たり聞いたりしたことを1つ書き留められそうですか。",
    "video": "すでにある動画はありますか。無ければ撮らなくて構いません。",
}

HINTS: Final[dict[SlotCode, str]] = {
    "place": "オンライン中心なら本社の所在地で構いません",
    "partner": "名前を出してよいかは後で確認できます",
    "people": "スタッフ, お客さま, 学生。いない場合もそのまま教えてください",
    "novelty": "「初」が無ければ「◯年目」「◯回目」でも構いません",
    "observation": "数字は要りません。ひとことで構いません",
    "video": "無い場合は「無い」で構いません",
}

# 顧客に見せる, 埋まったときの意味。数値も効果の断定も書かない
EFFECTS: Final[dict[SlotCode, str]] = {
    "place": "市区町村名を1つ入れると, その地域の経済新聞と地方紙が拾います。",
    "partner": "相手先の名前が入ると, 相手側の関係者にも届きます。",
    "people": "その場にいる人が写っていると, 何が起きたのかが伝わります。",
    "novelty": "「初」が言い切れると, 何が新しいのかが読み手に伝わります。",
    "observation": "その場で見えたことが1つあると, 発表文が具体的になります。",
    "video": "動画があれば添えられます。無ければ撮らなくて構いません。",
}

# 判定クエリC を通り, 因果を書いてよいスロット。通らなかったものは機能説明に留める(§6.5)
CAUSAL_SLOTS: Final[frozenset[SlotCode]] = frozenset({"place"})

# 読み取れなかったとき1回だけ聞き直す。place だけなのは効果量が突出しているため(同 §4)
RETRY_SLOTS: Final[frozenset[SlotCode]] = frozenset({"place"})

FOLLOW_UPS: Final[dict[SlotCode, str]] = {
    "place": "差し支えなければ, 市区町村か都道府県だけでも教えてください。",
}
