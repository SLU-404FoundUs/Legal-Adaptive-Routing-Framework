## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/safety_audit/response_audit.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Internal audit component. Handles the LLM call, <think> block stripping,
##        and JSON verdict parsing. Does NOT orchestrate routes, strictness labels,
##        or safeguard messages — those belong to the facade (SafetyAuditModule).
## @deps src.adaptive_routing.core.engine, src.adaptive_routing.config, json, re, logging

import json
import re
import logging
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

logger = logging.getLogger(__name__)


class ResponseAuditor:
    """
    @class ResponseAuditor
    @desc_ Pure audit engine. Receives a user query and LLM response, calls the
           audit LLM (Gemma 4), strips reasoning artifacts, and returns a structured
           verdict dict. Has no knowledge of routes, strictness tiers, or safeguard logic.
    @attr_ _engine : (LLMRequestEngine) The LLM engine for the audit call.
    @attr_ _system_prompt : (str) System instructions for the audit LLM.
    """

    def __init__(self, engine=None, system_prompt=None):
        """
        @func_ __init__
        @params engine : (LLMRequestEngine, optional) Audit LLM engine. Auto-created from config if None.
        @params system_prompt : (str, optional) System instructions. Default from config if None.
        """
        self._engine = engine or LLMRequestEngine(
            model=FrameworkConfig._VERIFICATION_DEEP_AUDIT_MODEL,
            temperature=FrameworkConfig._VERIFICATION_DEEP_AUDIT_TEMP,
            max_tokens=FrameworkConfig._VERIFICATION_DEEP_AUDIT_MAX_TOKENS,
            use_system_role=True,
            include_reasoning=FrameworkConfig._VERIFICATION_REASONING,
            reasoning_effort=FrameworkConfig._VERIFICATION_REASONING_EFFORT
        )
        self._system_prompt = system_prompt or FrameworkConfig._VERIFICATION_INSTRUCTIONS

        logger.info(
            f"[ResponseAuditor] Initialized — model={FrameworkConfig._VERIFICATION_DEEP_AUDIT_MODEL}, "
            f"reasoning={FrameworkConfig._VERIFICATION_REASONING}"
        )

    def _evaluate_(self, query, response, history=None, system_instructions=None):
        """
        @func_ _evaluate_
        @params query : (str) The user's normalized inquiry.
        @params response : (str) The LLM-generated response to audit.
        @params history : (list, optional) The conversation history.
        @params system_instructions : (str, optional) Override for audit system instructions.
        @returns (dict) Structured verdict with keys: verdict, confidence, explanation.
                 verdict is 'PASS' or 'FAIL'.
                 confidence is a float (0.0–1.0).
                 explanation is a 1-sentence reason from the audit LLM.
        @desc_ Sends the query-response pair to the audit LLM, strips <think> blocks,
               and parses the JSON verdict. On failure, returns a conservative FAIL.
        """
        if history:
            history_text = "[CONVERSATION HISTORY]\n"
            for msg in history:
                role_str = "USER" if msg.get("role") == "user" else "ASSISTANT"
                history_text += f"{role_str}: {msg.get('content', '')}\n"
            
            audit_prompt = (
                f"{history_text}\n"
                f"[CURRENT USER QUERY]:\n{query}\n\n"
                f"[AI RESPONSE TO AUDIT]:\n{response}\n\n"
                "Output JSON only."
            )
        else:
            audit_prompt = (
                f"USER QUERY:\n{query}\n\n"
                f"AI RESPONSE:\n{response}\n\n"
                "Output JSON only."
            )

        try:
            active_system_prompt = system_instructions or self._system_prompt
            raw_output = self._engine._get_completion_(audit_prompt, active_system_prompt)
            logger.info(f"[ResponseAuditor] Raw output: {raw_output[:300]}")

            ## @logic_ Strip <think> blocks — reasoning must NOT affect the verdict
            clean_output = re.sub(r'<think>[\s\S]*?</think>', '', raw_output, flags=re.IGNORECASE).strip()
            ## @logic_ Handle unclosed <think> blocks (streaming edge case)
            clean_output = re.sub(r'<think>[\s\S]*$', '', clean_output, flags=re.IGNORECASE).strip()

            ## @logic_ Parse structured JSON verdict
            json_match = re.search(r'\{.*\}', clean_output, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                verdict_raw = str(result.get("verdict", "FAIL")).upper().strip()
                confidence = float(result.get("confidence", 0.0))
                reason = result.get("reason", "No explanation provided.")

                logger.info(f"[ResponseAuditor] Verdict={verdict_raw}, Confidence={confidence:.2f}, Reason={reason}")

                return {
                    "verdict": verdict_raw,
                    "confidence": round(confidence, 4),
                    "explanation": reason
                }

        except json.JSONDecodeError as e:
            logger.error(f"[ResponseAuditor] JSON parse failed: {e}")
        except Exception as e:
            logger.error(f"[ResponseAuditor] Audit call failed: {e}")

        ## @logic_ Fallback: parsing failure → conservative FAIL (better to retry than pass bad output)
        return {
            "verdict": "FAIL",
            "confidence": 0.0,
            "explanation": "Audit evaluation could not be completed — treating as non-compliant for safety."
        }
