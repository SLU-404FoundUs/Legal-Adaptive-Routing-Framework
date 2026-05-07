## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/safety_audit/__init__.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Facade module for the Safety Audit Layer. Orchestrates route-based audit decisions,
##        delegates the actual LLM evaluation to the internal ResponseAuditor, and provides
##        the safeguard apology message. Follows the same orchestrator/facade pattern as
##        TriageModule and SemanticRouterModule.
## @deps src.adaptive_routing.modules.safety_audit.response_audit, src.adaptive_routing.config, logging

import logging
from src.adaptive_routing.modules.safety_audit.response_audit import ResponseAuditor
from src.adaptive_routing.config import FrameworkConfig

logger = logging.getLogger(__name__)


## @const_ ROUTE_STRICTNESS_MAP : Maps route names to config attribute suffixes.
ROUTE_STRICTNESS_MAP = {
    "Casual-LLM": "CASUAL",
    "General-LLM": "GENERAL",
    "Reasoning-LLM": "REASONING",
}


class SafetyAuditModule:
    """
    @class SafetyAuditModule
    @desc_ Facade that orchestrates the Safety Audit Layer. Acts as the single entry point
           for WEB.py and CLI.py. Handles:
           - Route-based skip logic (Casual routes are auto-compliant)
           - Empty response guarding
           - Dynamic strictness resolution per route
           - Delegating audit evaluation to the internal ResponseAuditor
           - Providing the safeguard apology message
    @attr_ _auditor : (ResponseAuditor) The internal audit component.
    @attr_ _persistence : (int) Max re-generation attempts before safeguarding.
    """

    def __init__(self, auditor=None, persistence=None):
        """
        @func_ __init__
        @params auditor : (ResponseAuditor, optional) Internal audit component. Auto-created if None.
        @params persistence : (int, optional) Max retry attempts. Default from config.
        """
        self._auditor = auditor or ResponseAuditor()
        self._persistence = persistence if persistence is not None else FrameworkConfig._VERIFICATION_PERSISTENCE

        logger.info(
            f"[SafetyAuditModule] Initialized — persistence={self._persistence}, "
            f"strictness=[Casual={FrameworkConfig._VERIFICATION_STRICTNESS_CASUAL}, "
            f"General={FrameworkConfig._VERIFICATION_STRICTNESS_GENERAL}, "
            f"Reasoning={FrameworkConfig._VERIFICATION_STRICTNESS_REASONING}]"
        )

    @staticmethod
    def _get_strictness_for_route_(route):
        """
        @func_ _get_strictness_for_route_
        @params route : (str) The classified route.
        @returns (float) The strictness threshold for the given route.
        @desc_ Resolves the dynamic strictness threshold from FrameworkConfig based on the route.
        """
        suffix = ROUTE_STRICTNESS_MAP.get(route, "GENERAL")
        return getattr(FrameworkConfig, f"_VERIFICATION_STRICTNESS_{suffix}", 0.50)

    def _run_audit_(self, normalized_query, response_text, route, history=None):
        """
        @func_ _run_audit_
        @params normalized_query : (str) The user's normalized inquiry from Triage.
        @params response_text : (str) The final LLM-generated response.
        @params route : (str) The classified route (Casual-LLM, General-LLM, Reasoning-LLM).
        @returns (dict) Contains 'verdict' (COMPLIANT/NON_COMPLIANT), 'confidence', 'explanation',
                 'strictness', 'route'.
        @desc_ Main entry point. Handles skip logic and guards, then delegates to the
               internal ResponseAuditor for the actual LLM evaluation.
        """
        ## @logic_ Skip audit entirely for casual routes
        if route == "Casual-LLM":
            logger.info("[SafetyAudit] Casual route — auto-COMPLIANT.")
            return {
                "verdict": "COMPLIANT", "confidence": 1.0,
                "explanation": "Casual route — audit skipped.",
                "strictness": FrameworkConfig._VERIFICATION_STRICTNESS_CASUAL,
                "route": route
            }

        ## @logic_ Guard: empty or whitespace-only response
        if not response_text or not response_text.strip():
            logger.warning("[SafetyAudit] Empty response — NON_COMPLIANT.")
            strictness = self._get_strictness_for_route_(route)
            return {
                "verdict": "NON_COMPLIANT", "confidence": 1.0,
                "explanation": "Empty response generated.",
                "strictness": strictness, "route": route
            }

        ## @logic_ Resolve dynamic strictness for this route
        strictness = self._get_strictness_for_route_(route)

        ## @logic_ Delegate to internal auditor for the LLM evaluation
        audit_result = self._auditor._evaluate_(normalized_query, response_text, history=history)

        ## @logic_ Map raw verdict (PASS/FAIL) to framework verdict (COMPLIANT/NON_COMPLIANT)
        raw_verdict = audit_result.get("verdict", "FAIL")
        framework_verdict = "COMPLIANT" if raw_verdict == "PASS" else "NON_COMPLIANT"

        logger.info(
            f"[SafetyAudit] Verdict={framework_verdict} (raw={raw_verdict}), "
            f"Confidence={audit_result.get('confidence')}, Route={route}, Strictness={strictness}"
        )

        return {
            "verdict": framework_verdict,
            "confidence": audit_result.get("confidence", 0.0),
            "explanation": audit_result.get("explanation"),
            "strictness": strictness,
            "route": route
        }

    @staticmethod
    def _build_safeguard_message_():
        """
        @func_ _build_safeguard_message_
        @returns (str) The safeguarding apology message.
        @desc_ Returns the message displayed after all persistence attempts are exhausted.
        """
        return (
            "I sincerely apologize, but after multiple attempts, I was unable to generate a response "
            "that adequately addresses your inquiry under our safeguarding rules and quality standards. "
            "This may happen when your question requires information outside our current legal scope.\n\n"
            "Please try rephrasing your question, or reach out directly to:\n"
            "• **DMW** (Department of Migrant Workers) — for employment and recruitment concerns\n"
            "• **OWWA** (Overseas Workers Welfare Administration) — for welfare and repatriation assistance\n\n"
            "I'm here to help with Philippine and Hong Kong labor law questions whenever you're ready."
        )
