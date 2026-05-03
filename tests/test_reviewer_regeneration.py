from __future__ import annotations

import unittest

from anki_ai.reviewer_regeneration import (
    _combine_answer_and_explanation,
    _extract_card_text,
    _manifest_css_files,
    _split_combined_answer,
    _write_regenerated_fields,
)


class FakeNote:
    def __init__(self, fields: dict[str, str]) -> None:
        self.fields = dict(fields)

    def keys(self) -> list[str]:
        return list(self.fields)

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value


class FakeCard:
    def __init__(self, note: FakeNote) -> None:
        self._note = note

    def note(self) -> FakeNote:
        return self._note


class ReviewerRegenerationHelpersTest(unittest.TestCase):
    def test_split_combined_answer_extracts_explanation(self) -> None:
        answer, explanation = _split_combined_answer(
            "Direct answer\n\nExplanation:\nSupporting context."
        )

        self.assertEqual(answer, "Direct answer")
        self.assertEqual(explanation, "Supporting context.")

    def test_combine_answer_and_explanation_omits_empty_explanation(self) -> None:
        self.assertEqual(_combine_answer_and_explanation("Answer", ""), "Answer")
        self.assertEqual(_combine_answer_and_explanation("Answer", None), "Answer")

    def test_extract_card_text_supports_basic_combined_back(self) -> None:
        card = FakeCard(
            FakeNote(
                {
                    "Front": "What does retrieval practice strengthen?",
                    "Back": "Recall\n\nExplanation:\nIt reinforces retrieval paths.",
                }
            )
        )

        self.assertEqual(
            _extract_card_text(card),
            {
                "question": "What does retrieval practice strengthen?",
                "answer": "Recall",
                "explanation": "It reinforces retrieval paths.",
            },
        )

    def test_write_answer_preserves_combined_explanation(self) -> None:
        note = FakeNote(
            {
                "Front": "What does retrieval practice strengthen?",
                "Back": "Recall\n\nExplanation:\nIt reinforces retrieval paths.",
            }
        )

        _write_regenerated_fields(
            note,
            mode="answer",
            answer="Long-term recall",
            explanation=None,
        )

        self.assertEqual(
            note.fields["Back"],
            "Long-term recall\n\nExplanation:\nIt reinforces retrieval paths.",
        )

    def test_write_answer_and_explanation_uses_separate_field_when_available(
        self,
    ) -> None:
        note = FakeNote(
            {
                "Front": "What does retrieval practice strengthen?",
                "Back": "Recall",
                "Explanation": "Old context.",
            }
        )

        _write_regenerated_fields(
            note,
            mode="answer_and_explanation",
            answer="Long-term recall",
            explanation="It reinforces retrieval paths.",
        )

        self.assertEqual(note.fields["Back"], "Long-term recall")
        self.assertEqual(
            note.fields["Explanation"],
            "It reinforces retrieval paths.",
        )

    def test_manifest_css_files_includes_imported_chunk_css(self) -> None:
        manifest = {
            "src/reviewer.tsx": {
                "file": "assets/reviewer.js",
                "imports": ["_shared.js"],
            },
            "_shared.js": {
                "file": "assets/shared.js",
                "css": ["assets/styles.css"],
            },
        }

        self.assertEqual(
            _manifest_css_files(manifest, manifest["src/reviewer.tsx"]),
            ["assets/styles.css"],
        )


if __name__ == "__main__":
    unittest.main()
