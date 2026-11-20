"""Repository for manual-extracted DHO804 knowledge records."""
import json
import re
from pathlib import Path

class ManualKnowledgeRepository:
    def __init__(self, path="data/knowledge/DHO804/manual_extracted/knowledge_records.jsonl"):
        self.path=Path(path); self.records=[json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
    def all(self): return list(self.records)
    def by_id(self, record_id): return [r for r in self.records if r.get("id")==record_id]
    def search(self, query="", *, record_type=None, chapter_id=None, limit=10):
        if limit < 1:
            return []
        terms = self._terms(query)
        query_text = str(query or "").casefold()
        results=[]
        for record in self.records:
            if record_type and record.get("record_type")!=record_type: continue
            if chapter_id and record.get("chapter_id")!=chapter_id: continue
            # Source images/tables can be very large and tend to repeat words;
            # rank semantic fields first and use provenance only as a fallback.
            semantic = " ".join(str(record.get(key, "")) for key in ("id", "name", "description", "data")).casefold()
            provenance = " ".join(str(record.get(key, "")) for key in ("source_text", "source_tables", "chapter_title")).casefold()
            haystack = semantic + " " + provenance
            score = 0
            for term in terms:
                score += semantic.count(term) * 4 + provenance.count(term)
            name = str(record.get("name", "")).casefold()
            description = str(record.get("description", "")).casefold()
            if "测量" in query_text:
                score += name.count("测量") * 12 + description.count("测量") * 3
                if any(feature in query_text for feature in ("峰峰值", "最大值", "最小值", "频率", "周期", "延迟", "相位")):
                    if "选择测量参数" in name:
                        score += 30
                    elif "进入测量菜单" in name:
                        score += 20
                    elif "选择测量源" in name:
                        score += 15
            for feature in ("峰峰值", "最大值", "最小值", "频率", "周期", "延迟", "相位"):
                if feature in query_text:
                    score += name.count(feature) * 12 + description.count(feature) * 3
            if terms and score == 0:
                # A contiguous Chinese query can still be useful when no
                # whitespace is present (for example ``测量峰峰值``).
                compact = re.sub(r"\s+", "", query.casefold())
                if compact and compact in haystack:
                    score = 2
            if terms and score==0: continue
            results.append((score,record))
        results.sort(key=lambda pair:(pair[0], pair[1].get("confidence",0) or 0),reverse=True)
        return [record for _,record in results[:limit]]

    @staticmethod
    def _terms(query: str) -> list[str]:
        """Tokenize mixed Chinese/English queries without requiring spaces."""
        text = str(query or "").casefold()
        # Preserve model identifiers and English labels as whole tokens.
        ascii_terms = re.findall(r"[a-z][a-z0-9_-]*|ch\s*[1-4]", text)
        chinese = re.sub(r"[a-z0-9_\-]+", " ", text)
        # Chinese single characters are too broad; use overlapping bigrams and
        # retain common measurement phrases as complete tokens.
        compact = re.sub(r"\s+", "", chinese)
        bigrams = [compact[i:i + 2] for i in range(len(compact) - 1)]
        stop = set("的了和与请帮我一下进行需要关于测量一个示波器" )
        terms = [t for t in ascii_terms if t.strip()]
        terms.extend(t for t in bigrams if t[0] not in stop and t[1] not in stop)
        if compact and len(compact) <= 8 and compact not in stop:
            terms.append(compact)
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(terms))
