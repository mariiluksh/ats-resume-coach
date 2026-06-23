"""Curated skill and ATS signal taxonomy.

The list is intentionally compact and intern-oriented. It can be extended with
local private profiles without committing derived data.
"""

from __future__ import annotations


SKILL_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "programming": {
        "python": ("python",),
        "java": ("java",),
        "javascript": ("javascript", "js", "node.js", "nodejs"),
        "typescript": ("typescript", "ts"),
        "c++": ("c++", "cpp"),
        "c#": ("c#", "csharp"),
        "go": ("golang", "go language"),
        "r": (" r ", "r programming"),
        "sql": ("sql",),
    },
    "data": {
        "pandas": ("pandas",),
        "numpy": ("numpy",),
        "scikit-learn": ("scikit-learn", "sklearn"),
        "machine learning": ("machine learning", "ml model", "classification", "regression"),
        "data analysis": ("data analysis", "data analytics", "eda", "exploratory analysis"),
        "visualization": ("visualization", "tableau", "power bi", "matplotlib", "seaborn"),
    },
    "web": {
        "html": ("html",),
        "css": ("css",),
        "react": ("react", "react.js", "reactjs"),
        "fastapi": ("fastapi",),
        "django": ("django",),
        "flask": ("flask",),
        "rest api": ("rest api", "restful", "api integration"),
    },
    "tools": {
        "git": ("git", "github", "gitlab"),
        "docker": ("docker", "container"),
        "linux": ("linux", "unix", "bash", "shell"),
        "excel": ("excel", "spreadsheets", "google sheets"),
        "jira": ("jira", "agile board"),
    },
    "cloud": {
        "aws": ("aws", "amazon web services"),
        "gcp": ("gcp", "google cloud"),
        "azure": ("azure",),
        "firebase": ("firebase",),
    },
    "professional": {
        "communication": ("communication", "stakeholder", "presentation"),
        "collaboration": ("collaboration", "teamwork", "cross-functional"),
        "documentation": ("documentation", "technical writing", "readme"),
        "testing": ("testing", "unit test", "pytest", "jest", "qa"),
    },
}


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "education": ("education", "university", "college", "degree", "coursework", "gpa"),
    "experience": ("experience", "employment", "work history", "internship"),
    "projects": ("projects", "portfolio", "capstone", "hackathon"),
    "skills": ("skills", "technical skills", "technologies", "tools"),
    "summary": ("summary", "profile", "objective", "about"),
}


ACTION_VERBS = {
    "built",
    "created",
    "implemented",
    "improved",
    "reduced",
    "increased",
    "analyzed",
    "automated",
    "designed",
    "deployed",
    "tested",
    "documented",
    "collaborated",
    "presented",
    "optimized",
    "trained",
}


WEAK_PHRASES = {
    "responsible for",
    "worked on",
    "helped with",
    "assisted with",
    "familiar with",
    "participated in",
    "various tasks",
    "etc",
}


ROLE_LEVEL_SIGNALS: dict[str, tuple[str, ...]] = {
    "intern": ("intern", "internship", "trainee", "student", "co-op", "placement"),
    "entry-level": ("entry level", "entry-level", "junior", "graduate", "new grad"),
    "mid/senior": ("senior", "lead", "principal", "staff", "manager"),
}

