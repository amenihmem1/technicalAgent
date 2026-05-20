from typing import Any

VALID_PHASES = ("QUESTION_1", "QUESTION_2", "QUESTION_3", "QUESTION_4", "FINAL")
SKILL_KEYS = ("question_score",)
MAX_EVIDENCE_CHARS = 400
MAX_NOTES = 5
FRENCH_MARKERS = frozenset({
    " je ", " vous ", " mon ", " ma ", " mes ", " bonjour ", " merci ",
    " parcours ", " equipe ", " entreprise ", " poste ", " entretien ",
    " suis ", " avec ", " pour ", " une ", " des ", " de ", " du ",
})
ENGLISH_MARKERS = frozenset({
    " i ", " i'm ", " im ", " my ", " me ", " ready ", " hello ", " hi ",
    " thanks ", " thank you ", " team ", " company ", " role ", " position ",
    " interview ", " experience ", " with ", " for ", " the ",
})
GENERIC_PROJECT_FILTER = frozenset({
    "habitu", "interet", "j'apprecie", "je souhaite", "au cours de mon parcours",
    "projets academiques", "vision globale", "environnement stimulant",
    "contribuer", "apprendre", "progresser", "competences", "skills",
})
MAX_ANCHOR_LENGTH = 80
MAX_PREVIEW_LENGTH = 280
MAX_CONTEXT_SNIPPET = 150
MAX_LAST_ANSWER_FOCUS = 120

RH_TECH_MARKERS = (
    "optimiser",
    "optimisation",
    "performance",
    "architecture",
    "algorith",
    "temps reel",
    "implementation",
    "fonctionnalite",
    "code",
    "api",
    "filtrage",
    "mise en production",
    "production",
    "deploiement",
    "front-end",
    "back-end",
    "release",
    "module",
    "modules",
    "frontend",
    "backend",
    "base de donnees",
    "interface",
    "endpoint",
    "endpoints",
    "architecture",
    "performance",
    "implementation",
    "feature",
    "features",
    "release",
    "deployment",
    "database",
)

RH_ALLOWED_MARKERS = (
    "equipe",
    "collaboration",
    "communi",
    "priorit",
    "organis",
    "conflit",
    "blocage",
    "autonomie",
    "feedback",
    "motiva",
    "apprent",
    "role",
    "desaccord",
    "relation",
    "coordination",
    "team",
    "collabor",
    "communic",
    "priority",
    "organ",
    "conflict",
    "blocker",
    "autonomy",
    "motivat",
    "learn",
    "disagree",
    "relationship",
)

RH_MOTIVATION_MARKERS = (
    "motiva",
    "motive",
    "envie",
    "rejoindre",
    "poste",
    "entreprise",
    "pourquoi vous",
    "pourquoi souhaitez",
    "attire",
    "interesse",
    "environnement",
    "carriere",
    "evolution",
    "progression",
    "avenir",
    "role",
    "mission",
    "why do you",
    "why are you",
    "motivat",
    "join",
    "company",
    "position",
    "interested",
    "career",
    "growth",
    "future",
)

INTERVIEW_JSON_SCHEMA: dict[str, Any] = {
    "name": "interview_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "phase": {"type": "string", "enum": list(VALID_PHASES)},
            "question_index": {"type": "integer", "minimum": 1},
            "say": {"type": "string"},
            "score_partial": {
                "type": "object",
                "properties": {
                    key: {"type": "integer", "minimum": 0, "maximum": 5}
                    for key in SKILL_KEYS
                },
                "required": list(SKILL_KEYS),
                "additionalProperties": False,
            },
            "notes": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_NOTES},
            "final_report": {
                "type": ["object", "null"],
                "properties": {
                    "summary": {"type": "string"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "watchouts": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {"type": "string"},
                },
                "required": ["summary", "strengths", "watchouts", "recommendation"],
                "additionalProperties": False,
            },
        },
        "required": ["phase", "question_index", "say", "score_partial", "notes", "final_report"],
        "additionalProperties": False,
    },
}
