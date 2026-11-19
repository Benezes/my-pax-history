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
    PEC_THRESHOLD,
    REJECTION_CAPITAL_REFUND,
)
from app.engine.apply import apply_delta, sync_derived
from app.engine.congress import pass_chance, projected_votes, roll_vote, vote_threshold
from app.engine.costs import compute_cost, heuristic_proposal
from app.engine.election import compose_congress, inaugurate, simulate_election, validate_proposals
from app.engine.mandate import assess_mandate, year_decay
from app.engine.newgame import create_new_game
from app.engine.turn import _apply_proposal, _fallback_report
from app.formatters import br_num
from app.llm.mock import MockProvider, match_proposal
from app.models import ActionProposal, CampaignClassification, CampaignProposalHint, GameState, ResolvedAction


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

    def test_honeymoon_majority_aligned_ordinary_bill_usually_passes(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.9, 0.9), seed=11, difficulty="medio")
        inaugurate(state, result)
        chamber_base = (
            state.congress.chamber.government + state.congress.chamber.allied
        ) / state.congress.chamber.seats
        senate_base = (
            state.congress.senate.government + state.congress.senate.allied
        ) / state.congress.senate.seats
        self.assertGreaterEqual(chamber_base, 0.5)
        proposal = ActionProposal(
            title="Reforma tributária",
            summary="Unificar tributos",
            category="fiscal",
            scope="medium",
            requires_congress=True,
            congress_difficulty=42,
        )
        text = "Proponho uma reforma tributária ampla, unificando PIS, Cofins e ICMS."
        mandate = assess_mandate(state, text, proposal)
        self.assertTrue(mandate.applied)
        self.assertGreaterEqual(mandate.capital_cut, 0.20)
        self.assertLessEqual(mandate.capital_cut, 0.35)
        self.assertGreaterEqual(mandate.pass_boost, 0.10)
        self.assertLessEqual(mandate.pass_boost, 0.20)
        chamber, senate = projected_votes(state, proposal)
        self.assertGreaterEqual(chamber + 1e-9, chamber_base)
        self.assertGreaterEqual(senate + 1e-9, senate_base)
        chance = pass_chance(state, proposal, mandate)
        self.assertGreaterEqual(chance, 0.70)
        self.assertLessEqual(chance, 0.90)

    def test_pec_uses_three_fifths_quorum(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.85, 0.85), seed=8, difficulty="medio")
        inaugurate(state, result)
        proposal = ActionProposal(
            title="PEC da reeleição indefinida",
            summary="Alterar a Constituição",
            category="institutional",
            scope="large",
            requires_congress=True,
            congress_difficulty=72,
            constitutional_amendment=True,
        )
        self.assertAlmostEqual(vote_threshold(proposal, proposal.title), PEC_THRESHOLD)
        class FailRng:
            def random(self) -> float:
                return 0.99

        passed, reason, chance = roll_vote(state, proposal, FailRng())
        self.assertFalse(passed)
        self.assertIn("três quintos", reason.lower())
        self.assertIn("rejeitada", reason.lower())
        self.assertNotIn("exploraram a fragilidade da base", reason.lower())
        self.assertLess(chance, 0.55)

    def test_projections_and_seats_follow_coalition(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.88, 0.88), seed=5, difficulty="medio")
        inaugurate(state, result)
        before = state.congress.chamber.government + state.congress.chamber.allied
        senate_before = state.congress.senate.government + state.congress.senate.allied
        proposal = ActionProposal(
            title="Projeto ordinário",
            summary="Lei comum",
            category="fiscal",
            scope="medium",
            requires_congress=True,
        )
        chamber_high, _ = projected_votes(state, proposal)
        apply_delta(state, "coalition_support", -12.0, 1.0)
        after = state.congress.chamber.government + state.congress.chamber.allied
        senate_after = state.congress.senate.government + state.congress.senate.allied
        self.assertLess(after, before)
        self.assertLess(senate_after, senate_before)
        self.assertAlmostEqual(
            after / state.congress.chamber.seats,
            state.congress.coalition_support / 100.0,
            delta=0.03,
        )
        chamber_low, _ = projected_votes(state, proposal)
        self.assertLess(chamber_low, chamber_high)

    def test_sync_derived_does_not_snap_senate_to_chamber(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.88, 0.88), seed=5, difficulty="medio")
        inaugurate(state, result)
        chamber_before = state.congress.chamber.government + state.congress.chamber.allied
        senate_before = state.congress.senate.government + state.congress.senate.allied
        sync_derived(state)
        self.assertEqual(
            chamber_before,
            state.congress.chamber.government + state.congress.chamber.allied,
        )
        self.assertEqual(
            senate_before,
            state.congress.senate.government + state.congress.senate.allied,
        )

    def test_ordinary_capital_is_modest_and_pec_costs_more(self):
        state = create_new_game("medio", "mock")
        ordinary = ActionProposal(
            title="Isenção do IR",
            summary="Faixa de isenção",
            category="fiscal",
            scope="medium",
            requires_congress=True,
            congress_difficulty=42,
        )
        pec = ActionProposal(
            title="PEC da reeleição indefinida",
            summary="Mudar a Constituição",
            category="institutional",
            scope="large",
            requires_congress=True,
            congress_difficulty=72,
            constitutional_amendment=True,
        )
        ordinary_cost = compute_cost(state, ordinary, "Isenção do imposto de renda até R$ 5 mil.")
        pec_cost = compute_cost(state, pec, "Enviar PEC da reeleição indefinida ao Congresso.")
        self.assertGreaterEqual(ordinary_cost.political, 8.0)
        self.assertLessEqual(ordinary_cost.political, 20.0)
        self.assertGreater(pec_cost.political, ordinary_cost.political)

    def test_rejection_lowers_approval(self):
        state = create_new_game("medio", "mock")
        before = state.indicators["approval"]
        proposal = ActionProposal(
            title="Reforma dura",
            summary="Texto",
            category="fiscal",
            scope="medium",
            requires_congress=True,
            congress_difficulty=90,
        )

        class FailRng:
            def random(self) -> float:
                return 0.99

        resolved = _apply_proposal(state, proposal, "Projeto de lei ordinária no Congresso.", FailRng())
        self.assertEqual(resolved.execution, "rejected")
        self.assertLess(state.indicators["approval"], before)
        self.assertIn("rejeitada", resolved.reason.lower())

    async def test_mock_classifies_campaign_offline(self):
        classified = await MockProvider().classify_campaign(PROPOSALS)
        self.assertEqual(len(classified.proposals), 3)
        self.assertTrue(classified.narrative)
        self.assertGreater(classified.proposals[0].popularity, 0.5)

    def test_br_num_rounds_half_up_like_the_header(self):
        self.assertEqual(br_num(34.5, 0), "35")
        self.assertEqual(br_num(34.4, 0), "34")
        self.assertEqual(round(34.5), 34)

    def test_report_mentions_delayed_approval_when_popularity_rises(self):
        state = create_new_game("medio", "mock")
        state.indicators["approval"] = 52.4
        resolved = [
            ResolvedAction(
                title="PEC duradoura",
                summary="Texto",
                passed=False,
                reason="Rejeitada no Congresso.",
                category="institutional",
                execution="rejected",
            )
        ]
        report = _fallback_report(state, resolved, approval_before=50.0, delayed_approval=True)
        self.assertIn("subiu", report.aprovacao)
        self.assertIn("defasad", report.aprovacao.lower())
        self.assertNotIn("desgastam a popularidade", report.aprovacao)

    def test_report_blames_congress_only_when_approval_falls(self):
        state = create_new_game("medio", "mock")
        state.indicators["approval"] = 48.2
        resolved = [
            ResolvedAction(
                title="PEC duradoura",
                summary="Texto",
                passed=False,
                reason="Rejeitada no Congresso.",
                category="institutional",
                execution="rejected",
            )
        ]
        report = _fallback_report(state, resolved, approval_before=50.0, delayed_approval=False)
        self.assertIn("recuou", report.aprovacao)
        self.assertIn("desgastam a popularidade", report.aprovacao)

    async def test_cost_preview_matches_offline_classifier(self):
        state = create_new_game("medio", "mock")
        result = simulate_election(PROPOSALS, _hints(3, 0.88, 0.88), seed=5, difficulty="medio")
        inaugurate(state, result)
        text = "Pacote de ferrovias e saneamento no Nordeste com obras transparentes."
        from app.engine.congress import stamp_amendment

        preview = match_proposal(state, text)
        stamp_amendment(preview, text)
        preview_mandate = assess_mandate(state, text, preview)
        preview_cost = compute_cost(state, preview, text, preview_mandate)
        bundle = await MockProvider().estimate_action(state, text)
        classified = bundle.interpretation.actions[0]
        stamp_amendment(classified, text)
        classified_mandate = assess_mandate(state, text, classified)
        classified_cost = compute_cost(state, classified, text, classified_mandate)
        self.assertEqual(preview.scope, classified.scope)
        self.assertEqual(preview_cost.political, classified_cost.political)
        heuristic = heuristic_proposal(text)
        self.assertNotEqual(preview.scope, heuristic.scope)


if __name__ == "__main__":
    unittest.main()
