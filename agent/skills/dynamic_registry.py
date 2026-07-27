import logging
from typing import List, Dict, Any, Callable
from langchain_core.tools import BaseTool

log = logging.getLogger(__name__)

class SkillRegistry:
    """
    Dynamic Tool & Skill Registry for AEGIS Agent System.
    Indexes tools with semantic tags and enables dynamic tool selection and routing.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(self, tool: BaseTool, tags: List[str] = None, category: str = "general"):
        """Register a tool or skill into the registry with classification tags."""
        name = tool.name
        self._tools[name] = tool
        self._metadata[name] = {
            "name": name,
            "description": tool.description,
            "tags": tags or [],
            "category": category
        }
        log.info("Registered skill '%s' in category '%s' with tags %s", name, category, tags)

    def get_tool(self, name: str) -> BaseTool:
        """Retrieve a specific tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """Return all registered tools as a list for binding."""
        return list(self._tools.values())

    def search_skills(self, query: str) -> List[BaseTool]:
        """
        Keyword-based or tag-based skill search for dynamic tool routing.
        Returns relevant tools matching query terms in name, description, or tags.
        """
        query_lower = query.lower()
        matched = []
        for name, tool in self._tools.items():
            meta = self._metadata[name]
            tags_text = " ".join(meta["tags"]).lower()
            desc_text = meta["description"].lower()
            
            if (query_lower in name.lower() or 
                any(term in tags_text for term in query_lower.split()) or 
                any(term in desc_text for term in query_lower.split())):
                matched.append(tool)

        return matched if matched else self.get_all_tools()

    def list_manifest(self) -> List[Dict[str, Any]]:
        """Return human-readable manifest of all active skills and tools."""
        return list(self._metadata.values())
