from typing import Final

# webclipping_list に転載元の PR TIMES 自身が1位で入る(2026-08-01 の実測で最多)。
# /reach の表示と wc_uniq の集計から除外しないと全企業に一律の下駄が乗る。
SELF_MEDIA: Final = "PR TIMES"

# API は1社分のインデックス参照しかしない。ETL の 150s とは用途が違うので短く固定する。
API_STATEMENT_TIMEOUT: Final = "10s"

# RDS は読み取り専用(requirements §7)。接続時に毎回宣言して書き込み経路を塞ぐ。
READ_ONLY_SQL: Final = "SET default_transaction_read_only = on"
