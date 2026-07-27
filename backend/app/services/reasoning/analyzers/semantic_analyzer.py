import os
import json
import re
from typing import Dict, Any, List, Set, Tuple
from loguru import logger

class SemanticAnalyzer:
    """Evaluates semantic features (DevOps, Cloud, AIML, Security, Leadership)
    using declarative configuration and populates the evidence graph.
    """

    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "semantic_groups.json")
            
        self.config_path = config_path
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load semantic groups configuration: {e}")
        # Fallback dictionary
        return {
            "Cloud Experience": {
                "keywords": ["aws", "azure", "gcp", "google cloud", "amazon web services", "cloud computing", "lambda", "ec2", "s3", "rds"],
                "description": "cloud infrastructure hosting and serverless applications"
            },
            "DevOps Experience": {
                "keywords": ["docker", "kubernetes", "jenkins", "ci/cd", "terraform", "ansible", "pipelines"],
                "description": "automation of building, testing, containerizing, and deploying projects"
            },
            "Security Experience": {
                "keywords": ["owasp", "oauth", "jwt", "ssl", "tls", "cryptography", "encryption", "firewall", "cybersecurity"],
                "description": "application security design and platform hardening"
            },
            "AI/ML Experience": {
                "keywords": ["tensorflow", "pytorch", "scikit-learn", "keras", "hugging face", "openai", "llama", "chatgpt", "machine learning", "deep learning"],
                "description": "developing artificial intelligence and machine learning pipelines"
            },
            "Leadership": {
                "keywords": ["team lead", "managed", "led", "mentored", "leadership", "director", "scrum master", "project manager"],
                "description": "coordinating developers and leading software release cycles"
            }
        }

    def analyze(self, profile_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Analyzes a profile's skills, projects, and history against semantic rules.
        Populates new fields and constructs the evidence graph.
        """
        evidence_graph = {}
        semantic_results = {}

        skills = [s.lower() for s in profile_data.get("skills", [])]
        projects = [p.lower() for p in profile_data.get("projects", [])]
        certs = [c.lower() if isinstance(c, str) else c.get("name", "").lower() for c in profile_data.get("certifications", [])]
        exp_history = [e.lower() for e in profile_data.get("experience_history", [])]

        raw_text_lower = raw_text.lower()

        for group_name, rule in self.rules.items():
            keywords = rule["keywords"]
            sources = []
            
            # Find evidence across sections
            matched_skills = [s for s in profile_data.get("skills", []) if s.lower() in keywords or any(kw in s.lower() for kw in keywords)]
            if matched_skills:
                sources.append({
                    "section": "Skills",
                    "text": ", ".join(matched_skills)
                })

            matched_projects = [p for p in profile_data.get("projects", []) if any(kw in p.lower() for kw in keywords)]
            if matched_projects:
                for mp in matched_projects:
                    sources.append({
                        "section": "Projects",
                        "text": mp
                    })

            matched_certs = [c if isinstance(c, str) else c.get("name", "") for c in profile_data.get("certifications", []) if any(kw in (c if isinstance(c, str) else c.get("name", "")).lower() for kw in keywords)]
            if matched_certs:
                sources.append({
                    "section": "Certifications",
                    "text": ", ".join(matched_certs)
                })

            matched_exp = [e for e in profile_data.get("experience_history", []) if any(kw in e.lower() for kw in keywords)]
            if matched_exp:
                for me in matched_exp:
                    sources.append({
                        "section": "Experience",
                        "text": me
                    })

            # If no matches in fields, scan raw text for keywords
            if not sources:
                matched_sentences = []
                for sentence in re.split(r'[.!?]\s', raw_text):
                    s_lower = sentence.lower()
                    if any(re.search(r'\b' + re.escape(kw) + r'\b', s_lower) for kw in keywords):
                        matched_sentences.append(sentence.strip())
                if matched_sentences:
                    sources.append({
                        "section": "Raw Text Mentions",
                        "text": " | ".join(matched_sentences[:2])
                    })

            # Calculate Evidence-Based Confidence
            if not sources:
                confidence = 0.0
                has_exp = False
            else:
                has_exp = True
                # Starting baseline
                confidence = 40.0
                
                # Check section categories
                sections_hit = {s["section"] for s in sources}
                
                # Boost confidence based on categories of evidence
                if "Projects" in sections_hit:
                    confidence += 25.0
                if "Experience" in sections_hit:
                    confidence += 20.0
                if "Certifications" in sections_hit:
                    confidence += 10.0
                if "Skills" in sections_hit and len(sections_hit) > 1:
                    confidence += 10.0
                
                # Boost based on keyword variety
                unique_kws_hit = set()
                sources_blob = " ".join(s["text"].lower() for s in sources)
                for kw in keywords:
                    if kw in sources_blob:
                        unique_kws_hit.add(kw)
                
                if len(unique_kws_hit) > 2:
                    confidence += 10.0
                elif len(unique_kws_hit) > 1:
                    confidence += 5.0

                confidence = min(98.0, confidence)

            field_key = group_name.lower().replace(" ", "_").replace("/", "_")
            
            # Populate semantic results
            semantic_results[field_key] = {
                "has_experience": has_exp,
                "confidence_score": confidence,
                "evidence_sources": sources,
                "description": rule["description"]
            }

            # Populate evidence graph
            if has_exp:
                evidence_graph[group_name] = {
                    "confidence": confidence,
                    "sources": sources
                }

        return {
            "semantic_features": semantic_results,
            "evidence_graph": evidence_graph
        }
