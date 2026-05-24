"""Phase B.1 — 出口エンジンの型定義。

intent_extractor の IntentResult を入力とし、ResponseResult を返す。
3 層: Router → Retriever → Composer。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KnowledgeChunk:
    """検索可能な知識単位。"""
    id: str
    title: str
    body: str
    category: str = ""                  # ga4, ec, sns, ... (intent_extractor の category と整合)
    intents: list[str] = field(default_factory=list)  # この chunk が答える intent (ask_lesson 等)
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class ResponseStrategy:
    """ルーターが決める応答戦略。"""
    template_id: str                    # 使用するテンプレ ID
    needs_retrieval: bool = False        # 知識検索が必要か
    politeness: str = "polite"           # polite | casual
    require_followup: bool = False       # フォローアップ質問を付けるか
    fallback_reason: str = ""            # 低信頼度時の理由 (clarify を出す根拠)


@dataclass
class ResponseResult:
    """出口エンジンの最終出力。"""
    text: str                            # 表示する回答文
    intent: str                          # 入力 intent (parity 確認用)
    template_id: str                     # 使われたテンプレ
    chunks: list[KnowledgeChunk] = field(default_factory=list)  # 採用した知識
    needs_clarification: bool = False    # ユーザーへの確認要請を含むか
    trace: dict = field(default_factory=dict)
