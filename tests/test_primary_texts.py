"""Corpus and retrieval smoke tests for the five conversational agents."""

import unittest

from backend.retrieval import search, retrieve_context
from tools import PHILOSOPHERS


SCENARIOS = {
    "plato": [("justice in a city", "Republic"), ("Socrates and the examined life", "Apology"), ("love and beauty", "Symposium")],
    "aristotle": [("virtue habit happiness", "Nicomachean"), ("citizenship and constitutions", "Politics"), ("tragedy and imitation", "Poetics")],
    "machiavelli": [("fortune and virtù", "Prince"), ("arms and rulers", "Prince"), ("republics and conflict", "Discourses")],
    "hume": [("cause effect experience", "Treatise"), ("custom and belief", "Enquiry"), ("design and natural religion", "Dialogues")],
    "kant": [("duty universal law", "Fundamental"), ("space and time knowledge", "Critique"), ("Prolegomena metaphysics science", "Prolegomena")],
}


class PrimaryTextRetrievalTests(unittest.TestCase):
    def test_all_five_have_three_retrieval_conversations(self) -> None:
        self.assertEqual(set(SCENARIOS), set(PHILOSOPHERS))
        for philosopher, scenarios in SCENARIOS.items():
            for query, expected_work in scenarios:
                passages = search(philosopher, query, limit=3)
                self.assertTrue(passages, f"no passages for {philosopher}: {query}")
                context = retrieve_context(philosopher, query, limit=3)
                self.assertIn("Primary-text reference", context)
                self.assertTrue(any(expected_work.lower() in passage.work.lower() for passage in passages), (philosopher, query, expected_work))


if __name__ == "__main__":
    unittest.main()
