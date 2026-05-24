"""Minimal QA example — end-to-end demonstration of nous-core.

Usage:
    python examples/minimal_qa.py
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

from nous import Brain  # noqa: E402 — stdout reconfig must run before imports


def main():
    # --- Set up a demo book ---
    tmp = tempfile.mkdtemp(prefix="nous_demo_")
    book_path = os.path.join(tmp, "company_manual.json")
    with open(book_path, "w", encoding="utf-8") as f:
        json.dump({
            "_meta": {"title": "社員規約", "version": "1.0"},
            "有給休暇": {
                "日数": "年10日（6ヶ月経過後）",
                "申請方法": "上長承認→人事システムで登録",
                "繰越": "最大20日まで翌年度に繰越可能",
            },
            "交通費": {
                "上限": "月3万円",
                "申請方法": "毎月末までに清算書を提出",
                "対象": "通勤・出張・顧客訪問",
            },
            "リモートワーク": {
                "条件": "入社6ヶ月以降、週3日まで",
                "申請方法": "前月15日までに申請",
                "機材": "会社貸与PC必須",
            },
        }, f, ensure_ascii=False, indent=2)

    # --- Create Brain, load book ---
    print("=" * 60)
    print("  nous-core Minimal QA Demo")
    print("=" * 60)
    brain = Brain()
    brain.load_book("company_manual", book_path)
    print(f"\n  Loaded book: {brain.books()}")
    print(f"  Summary: {brain.summary()}\n")

    # --- Ask questions ---
    questions = [
        "有給休暇は何日ですか？",
        "交通費の上限は？",
        "リモートワークはどういう条件？",
        "それの申請方法は？",  # 指示語解決
        "社長の名前は？",  # 知識外 → fallback
    ]

    for q in questions:
        print(f"Q: {q}")
        r = brain.ask(q)
        print(f"A: {r.text}")
        print(f"   [intent={r.intent}, book={r.source_book}, "
              f"key={r.source_key}, conf={r.confidence:.2f}, "
              f"fallback={r.used_fallback}]")
        print()

    print("=" * 60)
    print(f"  Final summary: {brain.summary()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
