from __future__ import annotations

import json
import unittest
from random import Random

from app.constants import (
    COALITION_CHAMBER_MAX,
    COALITION_CHAMBER_MIN,
    COALITION_SENATE_MAX,
    COALITION_SENATE_MIN,
    MANDATE_YEAR_DECAY,
    REJECTION_CAPITAL_REFUND,
)
from app.engine.costs import compute_cost
from app.engine.election import compose_congress, inaugurate, simulate_election, validate_proposals
from app.engine.mandate import assess_mandate, year_decay
from app.engine.newgame import create_new_game
from app.engine.turn import _apply_proposal
from app.llm.mock import MockProvider
from app.models import ActionProposal, CampaignClassification, CampaignProposalHint, GameState


def _hints(n: int, popularity: float, alignment: float) -> CampaignClassification:
    return CampaignClassification(
        proposals=[
            CampaignProposalHint(
                category="fiscal",
                popularity=popularity,
                alignment=alignment,
                keywords=["reforma", "tributaria", "imposto"],
                summary="Reforma tributária",
            )
            for _ in range(n)
        ],
        platform_coherence=popularity,
        narrative="Campanha de teste.",
    )


PROPOSALS = [
    "Reforma tributária ampla, unificando PIS, Cofins e ICMS com transição gradual.",
    "Pacote de saneamento e ferrovias no Nordeste com obras transparentes.",
    "Agenda de saúde da família e creches em municípios pobres.",
]


class ElectionEngineTests(unittest.IsolatedAsyncioTestCase):
    def test_strong_platform_can_win_first_round(self):
        result = simulate_election(PROPOSALS, _hints(3, 0.92, 0.9), seed=11, difficulty="medio")
        self.assertFalse(result.runoff)
        self.assertGreaterEqual(result.winner_share, 50.0)
        self.assertGreater(result.margin_pp, 0)
        self.assertAlmostEqual(sum(item.weight for item in result.proposals), 1.0, places=3)

    def test_weak_platform_goes_to_runoff(self):
        result = simulate_election(PROPOSALS, _hints(3, 0.2, 0.2), seed=3, difficulty="impossivel")
        self.assertTrue(result.runoff)
        self.assertIsNotNone(result.second_round_share)
        self.assertGreaterEqual(result.winner_share, 50.0)

    def test_same_seed_is_deterministic(self):
        a = simulate_election(PROPOSALS, _hints(3, 0.7, 0.7), seed=99, difficulty="medio")
        b = simulate_election(PROPOSALS, _hints(3, 0.7, 0.7), seed=99, difficulty="medio")
        self.assertEqual(a.model_dump(), b.model_dump())

    def test_proposal_validation(self):
        with self.assertRaises(ValueError):
            validate_proposals(["curta", "também curta"])
        with self.assertRaises(ValueError):
            validate_proposals(PROPOSALS + PROPOSALS)
        self.assertEqual(len(validate_proposals(PROPOSALS)), 3)

    def test_congress_stays_within_sane_bounds(self):
        state = create_new_game("medio", "mock")
        for margin, strength in ((1.0, 0.2), (8.0, 0.7), (20.0, 0.99)):
            congress = compose_congress(state.congress, margin, strength)
            chamber_share = (congress.chamber.government + congress.chamber.allied) / congress.chamber.seats
            senate_share = (congress.senate.government + congress.senate.allied) / congress.senate.seats
            self.assertGreaterEqual(chamber_share, COALITION_CHAMBER_MIN - 1e-9)
            self.assertLessEqual(chamber_share, COALITION_CHAMBER_MAX + 1e-9)
            self.assertGreaterEqual(senate_share, COALITION_SENATE_MIN - 1e-9)
            self.assertLessEqual(senate_share, COALITION_SENATE_MAX + 1e-9)
            self.assertEqual(
                congress.chamber.government
                + congress.chamber.allied
                + congress.chamber.opposition
                + congress.chamber.independent,
                congress.chamber.seats,
            )
            self.assertEqual(sum(p.chamber_seats for p in congress.parties), congress.chamber.seats)
            self.assertEqual(sum(p.senate_seats for p in congress.parties), congress.senate.seats)
            self.assertLess(chamber_share, 0.60)

    def test_mandate_decay_over_years(self):
        self.assertEqual(year_decay(0), MANDATE_YEAR_DECAY[0])
        self.assertEqual(year_decay(11), MANDATE_YEAR_DECAY[0])
        self.assertEqual(year_decay(12), MANDATE_YEAR_DECAY[1])
        self.assertEqual(year_decay(30), MANDATE_YEAR_DECAY[2])
        self.assertEqual(year_decay(40), MANDATE_YEAR_DECAY[3])

    def test_aligned_action_matches_campaign(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.8, 0.8), seed=state.seed, difficulty="medio")
        inaugurate(state, result)
        assessment = assess_mandate(
            state,
            "Proponho uma reforma tributária ampla, unificando impostos sobre consumo.",
        )
        self.assertTrue(assessment.matched)
        self.assertTrue(assessment.applied)
        self.assertIn("Mandato das urnas", assessment.note)
        year1 = assessment.bonus
        state.months_elapsed = 20
        later = assess_mandate(state, "Proponho uma reforma tributária ampla, unificando impostos sobre consumo.")
        self.assertLess(later.bonus, year1)

    def test_unrelated_action_does_not_match(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.8, 0.8), seed=state.seed, difficulty="medio")
        inaugurate(state, result)
        assessment = assess_mandate(state, "Comprar café especial para o Palácio e pintar uma sala.")
        self.assertFalse(assessment.applied)

    def test_mandate_reduces_political_cost(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.85, 0.85), seed=7, difficulty="medio")
        inaugurate(state, result)
        proposal = ActionProposal(
            title="Reforma tributária",
            summary="Unificar tributos",
            category="fiscal",
            scope="large",
            requires_congress=True,
            congress_difficulty=58,
        )
        text = "Proponho uma reforma tributária ampla, unificando PIS, Cofins e ICMS."
        with_bonus = compute_cost(state, proposal, text, assess_mandate(state, text, proposal))
        state.campaign = None
        without = compute_cost(state, proposal, text)
        self.assertLess(with_bonus.political, without.political)

    def test_rejection_refunds_half_the_capital(self):
        state = create_new_game("medio", "mock")
        before = state.indicators["political_capital"]
        proposal = ActionProposal(
            title="Reforma dura",
            summary="Texto",
            category="fiscal",
            scope="large",
            requires_congress=True,
            congress_difficulty=90,
        )
        class FailRng:
            def random(self) -> float:
                return 0.99

        resolved = _apply_proposal(state, proposal, "Reforma tributária ampla no Congresso.", FailRng())
        self.assertEqual(resolved.execution, "rejected")
        self.assertGreater(resolved.capital_refunded, 0)
        self.assertAlmostEqual(
            resolved.capital_refunded / max(0.01, resolved.political_cost + resolved.capital_refunded),
            REJECTION_CAPITAL_REFUND,
            places=2,
        )
        self.assertIn("devolvidos", resolved.reason)
        self.assertNotIn("parcialmente executada", resolved.reason.lower())
        self.assertLess(state.indicators["political_capital"], before)
        self.assertIn("capital político", resolved.reason.lower())

    def test_campaign_contradiction_is_blocked(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(
            [
                "Pacto democrático com respeito ao Congresso e ao Estado de direito.",
                "Responsabilidade fiscal com teto de gastos e equilíbrio das contas.",
                "Agenda de paz, direitos humanos e civilidade institucional.",
            ],
            CampaignClassification(
                proposals=[
                    CampaignProposalHint(
                        category="institutional",
                        popularity=0.8,
                        alignment=0.8,
                        keywords=["democracia", "congresso", "direito"],
                        summary="Pacto democrático",
                    ),
                    CampaignProposalHint(
                        category="fiscal",
                        popularity=0.7,
                        alignment=0.75,
                        keywords=["responsabilidade", "fiscal", "teto"],
                        summary="Responsabilidade fiscal",
                    ),
                    CampaignProposalHint(
                        category="institutional",
                        popularity=0.7,
                        alignment=0.7,
                        keywords=["paz", "direitos", "humanos"],
                        summary="Paz e direitos",
                    ),
                ],
                platform_coherence=0.8,
                narrative="Campanha institucional.",
            ),
            seed=4,
            difficulty="medio",
        )
        inaugurate(state, result)
        resolved = _apply_proposal(
            state,
            ActionProposal(title="Ruptura", summary="golpe", category="institutional", scope="massive"),
            "Vou furar o teto e gastar sem limite imprimindo dinheiro.",
            Random(2),
        )
        self.assertEqual(resolved.execution, "blocked")
        self.assertEqual(resolved.limit_kind, "campaign")
        self.assertIn("campanha", resolved.reason.lower())

    def test_unconstitutional_action_is_blocked(self):
        state = create_new_game("medio", "mock")
        resolved = _apply_proposal(
            state,
            ActionProposal(title="Ruptura", summary="golpe", category="institutional", scope="massive"),
            "Vou fechar o Congresso e dar um golpe.",
            Random(1),
        )
        self.assertEqual(resolved.execution, "blocked")
        self.assertEqual(resolved.limit_kind, "constitution")
        self.assertIn("constitucional", resolved.reason.lower())

    def test_old_save_without_campaign_still_loads(self):
        state = create_new_game("medio", "mock")
        payload = json.loads(state.model_dump_json())
        payload.pop("campaign", None)
        payload.pop("campaign_pending", None)
        loaded = GameState.model_validate(payload)
        self.assertIsNone(loaded.campaign)
        self.assertFalse(loaded.campaign_pending)
        self.assertEqual(loaded.status, "playing")

    async def test_mock_classifies_campaign_offline(self):
        classified = await MockProvider().classify_campaign(PROPOSALS)
        self.assertEqual(len(classified.proposals), 3)
        self.assertTrue(classified.narrative)
        self.assertGreater(classified.proposals[0].popularity, 0.5)


if __name__ == "__main__":
    unittest.main()
