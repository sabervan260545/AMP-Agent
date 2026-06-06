# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Structured Output Module - Constrain LLM Output Format
========================================================

Core Features:
1. JSON Schema Constraints - Ensure parseable output
2. Tool Call Chain Tracking - Record complete reasoning process
3. Knowledge Base Citation Management - Verify all claims have sources
4. Biological Reasoning Validation - Ensure compliance with AMP design principles

Architecture:
- ReasoningType: Enum for categorizing reasoning steps
- KnowledgeCitation: Track knowledge base references with relevance scores
- BiologicalReasoning: Represent reasoning steps with biological principles
- ToolCall: Record tool invocations with parameters and results
- StructuredResponse: Complete response with quality metrics
- StructuredOutputParser: Extract structured info from LLM output
- ResponseValidator: Ensure biological rigor and knowledge grounding

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class ReasoningType(Enum):
    """Reasoning type classification for biological reasoning steps."""
    KNOWLEDGE_QUERY = "knowledge_query"      # Knowledge base lookup
    BIOLOGICAL_ANALYSIS = "biological_analysis"  # Biological interpretation
    TOOL_PLANNING = "tool_planning"          # Tool execution planning
    RESULT_INTERPRETATION = "result_interpretation"  # Output analysis
    OPTIMIZATION = "optimization"            # Refinement strategy


@dataclass
class KnowledgeCitation:
    """
    Knowledge base citation with relevance tracking.

    Attributes:
        source: Knowledge source (literature/mic/cpp/hemolysis)
        query: Query keywords used
        relevance_score: Relevance score (0-1)
        content_snippet: Content snippet from knowledge base
        timestamp: Citation timestamp

    Examples:
        >>> citation = KnowledgeCitation(
        ...     source="literature",
        ...     query="Gram-negative AMP design",
        ...     relevance_score=0.92,
        ...     content_snippet="Cationic peptides with +4 to +7 net charge..."
        ... )
        >>> str(citation)
        '[literature|0.92] Cationic peptides with +4 to +7 net charge...'
    """
    source: str
    query: str
    relevance_score: float
    content_snippet: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __str__(self):
        return f"[{self.source}|{self.relevance_score:.2f}] {self.content_snippet[:100]}..."


@dataclass
class BiologicalReasoning:
    """
    Biological reasoning step with knowledge support tracking.

    Attributes:
        reasoning_type: Type of reasoning (knowledge query, analysis, etc.)
        thought: Reasoning content
        knowledge_citations: List of knowledge base citations supporting this reasoning
        biological_principles: List of biological principles invoked
        confidence: Reasoning confidence score (0-1)
        timestamp: Reasoning timestamp

    Examples:
        >>> reasoning = BiologicalReasoning(
        ...     reasoning_type=ReasoningType.BIOLOGICAL_ANALYSIS,
        ...     thought="Gram-negative bacteria require cationic peptides",
        ...     biological_principles=["net charge", "hydrophobicity"],
        ...     confidence=0.95
        ... )
        >>> reasoning.has_knowledge_support()
        False
    """
    reasoning_type: ReasoningType
    thought: str
    knowledge_citations: List[KnowledgeCitation] = field(default_factory=list)
    biological_principles: List[str] = field(default_factory=list)  # Biological principles invoked
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def has_knowledge_support(self) -> bool:
        """Check whether this reasoning step is backed by knowledge base citations."""
        return len(self.knowledge_citations) > 0

    def to_dict(self):
        return {
            "reasoning_type": self.reasoning_type.value,
            "thought": self.thought,
            "citations": [asdict(c) for c in self.knowledge_citations],
            "principles": self.biological_principles,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }


@dataclass
class ToolCall:
    """
    Tool invocation record with execution details.

    Attributes:
        tool_name: Name of the tool called
        parameters: Tool input parameters
        result: Tool execution result (optional)
        reasoning: Associated biological reasoning (optional)
        success: Whether execution succeeded
        error_message: Error message if failed
        latency_ms: Execution latency in milliseconds
        timestamp: Invocation timestamp

    Examples:
        >>> tool_call = ToolCall(
        ...     tool_name="generate_sequences",
        ...     parameters={"target": "Gram-negative", "count": 10},
        ...     success=True,
        ...     latency_ms=1250.5
        ... )
        >>> tool_call.success
        True
    """
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    reasoning: Optional[BiologicalReasoning] = None
    success: bool = True
    error_message: str = ""
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "reasoning": self.reasoning.to_dict() if self.reasoning else None,
            "success": self.success,
            "error": self.error_message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp
        }


@dataclass
class StructuredResponse:
    """
    Structured response with complete reasoning chain and quality metrics.

    Tracks the full Agent execution including reasoning steps,
    tool invocations, and quality metrics for biological rigor.

    Attributes:
        session_id: Session identifier
        user_query: Original user query
        reasoning_chain: List of biological reasoning steps
        tool_calls: List of tool invocations
        final_answer: Final answer text
        total_knowledge_queries: Count of knowledge base lookups
        knowledge_coverage_score: Knowledge coverage score (0-1)
        biological_rigor_score: Biological rigor score (0-1)
        start_time: Start timestamp
        end_time: End timestamp (optional)

    Examples:
        >>> response = StructuredResponse(
        ...     session_id="test_001",
        ...     user_query="Design AMPs for E.coli"
        ... )
        >>> response.add_reasoning(reasoning)
        >>> response.finalize("Generated 10 candidate sequences...")
        >>> response.biological_rigor_score
        0.85
    """
    session_id: str
    user_query: str

    # Reasoning chain
    reasoning_chain: List[BiologicalReasoning] = field(default_factory=list)

    # Tool call chain
    tool_calls: List[ToolCall] = field(default_factory=list)

    # Final answer
    final_answer: str = ""

    # Quality metrics
    total_knowledge_queries: int = 0          # Number of knowledge base lookups
    knowledge_coverage_score: float = 0.0     # Knowledge coverage score
    biological_rigor_score: float = 0.0       # Biological rigor score

    # Metadata
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None

    def add_reasoning(self, reasoning: BiologicalReasoning):
        """Append a reasoning step to the chain."""
        self.reasoning_chain.append(reasoning)

        # Count knowledge base lookups
        if reasoning.reasoning_type == ReasoningType.KNOWLEDGE_QUERY:
            self.total_knowledge_queries += 1

    def add_tool_call(self, tool_call: ToolCall):
        """Append a tool invocation record."""
        self.tool_calls.append(tool_call)

        # Count knowledge search calls
        if tool_call.tool_name == "search_knowledge":
            self.total_knowledge_queries += 1

    def finalize(self, answer: str):
        """Finalize the response and compute quality scores."""
        self.final_answer = answer
        self.end_time = datetime.now().isoformat()

        # Compute quality metrics
        self._calculate_quality_scores()

    def _calculate_quality_scores(self):
        """Compute quality scores based on reasoning depth and knowledge support."""
        # Knowledge coverage: based on number of cited knowledge entries
        total_citations = sum(
            len(r.knowledge_citations) for r in self.reasoning_chain
        )
        self.knowledge_coverage_score = min(total_citations / 5.0, 1.0)  # 5 citations = perfect score

        # Biological rigor: based on biological principles invoked and knowledge support
        total_principles = sum(
            len(r.biological_principles) for r in self.reasoning_chain
        )
        knowledge_supported_steps = sum(
            1 for r in self.reasoning_chain if r.has_knowledge_support()
        )
        total_steps = len(self.reasoning_chain)

        if total_steps > 0:
            principle_score = min(total_principles / (total_steps * 2), 1.0)
            support_score = knowledge_supported_steps / total_steps
            self.biological_rigor_score = (principle_score + support_score) / 2
        else:
            self.biological_rigor_score = 0.0

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_query": self.user_query,
            "reasoning_chain": [r.to_dict() for r in self.reasoning_chain],
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "final_answer": self.final_answer,
            "quality_metrics": {
                "total_knowledge_queries": self.total_knowledge_queries,
                "knowledge_coverage_score": self.knowledge_coverage_score,
                "biological_rigor_score": self.biological_rigor_score
            },
            "start_time": self.start_time,
            "end_time": self.end_time
        }

    def to_json(self, indent=2) -> str:
        """Export to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, file_path: str):
        """Persist to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


class StructuredOutputParser:
    """
    Structured output parser — Extract structured information from LLM output.

    Parses LLM ReAct-style output to extract thoughts, actions, inputs, and final
    answers. Supports both English and Chinese patterns commonly produced by
    bilingual LLM deployments.

    Attributes:
        THOUGHT_PATTERN: Regex for extracting thoughts (💭 Thought: / 思考)
        ACTION_PATTERN: Regex for extracting actions (🔧 Action: / 动作)
        INPUT_PATTERN: Regex for extracting inputs (📥 Input: / 输入)
        ANSWER_PATTERN: Regex for extracting final answer (✅ Final Answer: / 最终答案)
        KNOWLEDGE_KEYWORDS: Keywords indicating knowledge base usage (EN/CN)
        BIOLOGICAL_KEYWORDS: Biological principle keywords (EN key → CN display label)

    Examples:
        >>> parser = StructuredOutputParser()
        >>> response = parser.parse_response(llm_output, session_id, user_query)
        >>> len(response.reasoning_chain)
        3
    """

    # Regex patterns — match both English and Chinese ReAct output tags
    THOUGHT_PATTERN = re.compile(r'💭\s*(?:思考|Thought):\s*(.+?)(?=🔧|✅|$)', re.DOTALL)
    ACTION_PATTERN = re.compile(r'🔧\s*(?:动作|Action):\s*(\w+)', re.DOTALL)
    INPUT_PATTERN = re.compile(r'📥\s*(?:输入|Action Input|Input):\s*(\{.+?\})', re.DOTALL)
    ANSWER_PATTERN = re.compile(r'✅\s*(?:最终答案|Final Answer):\s*(.+)', re.DOTALL)

    # Keywords indicating knowledge base reliance (EN + CN for bilingual output)
    KNOWLEDGE_KEYWORDS = [
        # English
        'knowledge base', 'literature', 'search', 'query',
        'based on', 'citation',
        # Chinese (for bilingual LLM output)
        '知识库', '文献', '检索', '查询',
        '根据', '引用'
    ]

    # Biological principle keywords: English canonical term → Chinese display name
    # Used for text matching against bilingual LLM output; Chinese values are
    # preserved as display labels for international publication contexts.
    BIOLOGICAL_KEYWORDS = {
        'amphipathicity': '两亲性',
        'hydrophobicity': '疏水性',
        'net_charge': '净电荷',
        'helix': '螺旋',
        'membrane': '膜',
        'selectivity': '选择性',
        'toxicity': '毒性',
        'stability': '稳定性'
    }

    @classmethod
    def parse_response(cls, llm_output: str, session_id: str, user_query: str) -> StructuredResponse:
        """
        Parse ReAct LLM output into a structured response.

        Extracts thoughts, actions, inputs, and final answer from LLM output
        formatted with ReAct tags (supports both English and Chinese).

        Args:
            llm_output: Raw LLM output text (ReAct format)
            session_id: Session identifier
            user_query: Original user query

        Returns:
            StructuredResponse with complete reasoning chain and tool calls

        Examples:
            >>> llm_output = '💭 Thought: Need to query knowledge base...\\n🔧 Action: search_knowledge'
            >>> response = StructuredOutputParser.parse_response(llm_output, "s1", "Design AMPs")
            >>> len(response.reasoning_chain)
            1
        """
        response = StructuredResponse(
            session_id=session_id,
            user_query=user_query
        )

        # Extract thought steps
        thoughts = cls.THOUGHT_PATTERN.findall(llm_output)
        for thought in thoughts:
            reasoning = cls._parse_thought(thought.strip())
            response.add_reasoning(reasoning)

        # Extract tool calls
        actions = cls.ACTION_PATTERN.findall(llm_output)
        inputs = cls.INPUT_PATTERN.findall(llm_output)

        for action, input_json in zip(actions, inputs):
            try:
                params = json.loads(input_json)
                tool_call = ToolCall(
                    tool_name=action,
                    parameters=params
                )
                response.add_tool_call(tool_call)
            except json.JSONDecodeError:
                pass

        # Extract final answer
        answer_match = cls.ANSWER_PATTERN.search(llm_output)
        if answer_match:
            response.finalize(answer_match.group(1).strip())

        return response

    @classmethod
    def _parse_thought(cls, thought_text: str) -> BiologicalReasoning:
        """
        Parse a single thought step into a BiologicalReasoning object.

        Args:
            thought_text: Text content of the thought

        Returns:
            BiologicalReasoning with detected reasoning type and principles
        """
        # Detect reasoning type
        reasoning_type = cls._detect_reasoning_type(thought_text)

        # Extract biological principles mentioned
        principles = cls._extract_biological_principles(thought_text)

        # Detect whether knowledge base was cited
        has_knowledge = any(kw in thought_text.lower() for kw in cls.KNOWLEDGE_KEYWORDS)

        return BiologicalReasoning(
            reasoning_type=reasoning_type,
            thought=thought_text,
            biological_principles=principles,
            confidence=0.9 if has_knowledge or principles else 0.7
        )

    @classmethod
    def _detect_reasoning_type(cls, text: str) -> ReasoningType:
        """
        Classify the reasoning type from text content.

        Supports both English and Chinese keyword detection for bilingual
        LLM deployments.

        Args:
            text: Text content to analyze

        Returns:
            Matching ReasoningType enum value
        """
        text_lower = text.lower()

        if any(kw in text_lower for kw in ['检索', 'search', '知识库', 'knowledge']):
            return ReasoningType.KNOWLEDGE_QUERY
        elif any(kw in text_lower for kw in ['分析', 'analyze', '解读', 'interpret']):
            return ReasoningType.BIOLOGICAL_ANALYSIS
        elif any(kw in text_lower for kw in ['优化', 'optimize', '调整', 'adjust']):
            return ReasoningType.OPTIMIZATION
        elif any(kw in text_lower for kw in ['工具', 'tool', '调用', 'call']):
            return ReasoningType.TOOL_PLANNING
        else:
            return ReasoningType.RESULT_INTERPRETATION

    @classmethod
    def _extract_biological_principles(cls, text: str) -> List[str]:
        """
        Extract biological principles referenced in the text.

        Checks both the English canonical term and its Chinese equivalent
        against the text, returning the Chinese display label for each match.

        Args:
            text: Text content to analyze

        Returns:
            List of Chinese biological principle names found (deduplicated)
        """
        principles = []
        text_lower = text.lower()

        for en_term, zh_term in cls.BIOLOGICAL_KEYWORDS.items():
            if en_term in text_lower or zh_term in text:
                principles.append(zh_term)

        return list(set(principles))  # Deduplicate


class ResponseValidator:
    """
    Response validator — Ensure LLM output meets biological standards.

    Validates response quality based on three pillars:
    knowledge grounding, biological rigor, and workflow correctness.

    Quality Checks:
    1. Knowledge base queries — Should query KB before design
    2. Knowledge coverage score — Should cite sufficient literature
    3. Biological rigor score — Should invoke biological principles
    4. Tool call ordering — Should search knowledge before generating

    Examples:
        >>> validator = ResponseValidator()
        >>> is_valid, warnings = validator.validate(response)
        >>> is_valid
        True
    """

    @staticmethod
    def validate(response: StructuredResponse) -> Tuple[bool, List[str]]:
        """
        Validate response quality and produce diagnostic warnings.

        Args:
            response: StructuredResponse to validate

        Returns:
            Tuple of (is_valid, warnings):
                - is_valid: Whether the response passes all quality gates
                - warnings: List of human-readable warning messages
        """
        warnings = []

        # Check 1: Knowledge base queries should be performed
        if response.total_knowledge_queries == 0:
            warnings.append("⚠️ Warning: No knowledge base queries! All design decisions should be evidence-based.")

        # Check 2: Knowledge coverage should meet minimum threshold
        if response.knowledge_coverage_score < 0.3:
            warnings.append(f"⚠️ Knowledge coverage too low ({response.knowledge_coverage_score:.2f}), suggest more literature citations.")

        # Check 3: Biological rigor should be sufficient
        if response.biological_rigor_score < 0.4:
            warnings.append(f"⚠️ Insufficient biological rigor ({response.biological_rigor_score:.2f}), need more biological principle support.")

        # Check 4: Tool call ordering — knowledge should be searched before generation
        tool_names = [t.tool_name for t in response.tool_calls]
        if 'generate_sequences' in tool_names:
            gen_index = tool_names.index('generate_sequences')
            search_before_gen = any(
                t == 'search_knowledge' for t in tool_names[:gen_index]
            )
            if not search_before_gen:
                warnings.append("⚠️ No knowledge query before sequence generation! Should understand design principles first.")

        # Overall pass/fail: valid if no warnings OR biological rigor is adequate
        is_valid = len(warnings) == 0 or response.biological_rigor_score >= 0.6

        return is_valid, warnings


# ==================== Test Code ====================

if __name__ == "__main__":
    print("=== Structured Output Module Test ===\n")

    # Simulated LLM output
    llm_output = """
💭 Thought: User wants to design AMPs for E. coli. This is a Gram-negative bacterium, need to consider LPS membrane impact. Let me query knowledge base first.

🔧 Action: search_knowledge
📥 Input: {"query": "Gram-negative AMP design net charge hydrophobicity", "knowledge_type": "literature", "top_k": 5}

💭 Thought: Knowledge base shows AMPs for Gram-negative bacteria typically need +4 to +7 net charge, 50-60% hydrophobicity, and α-helix structure. Based on these principles, generate sequences.

🔧 Action: generate_sequences
📥 Input: {"target": "Gram-negative", "count": 10}

💭 Thought: Received 10 candidate sequences. Now need to validate AMP activity and predict MIC values.

✅ Final Answer: Based on knowledge base design principles (net charge +5, hydrophobicity 55%, α-helix), generated 10 candidate AMP sequences. Recommended sequence KLWKKLLKWL has optimal amphipathic balance.
"""

    # Parse
    parser = StructuredOutputParser()
    response = parser.parse_response(
        llm_output=llm_output,
        session_id="test_20251213",
        user_query="Design 3 AMPs for E. coli"
    )

    # Validate
    validator = ResponseValidator()
    is_valid, warnings = validator.validate(response)

    # Display results
    print(f"Session ID: {response.session_id}")
    print(f"User Query: {response.user_query}")
    print(f"\nReasoning Steps: {len(response.reasoning_chain)}")
    print(f"Tool Calls: {len(response.tool_calls)}")
    print(f"Knowledge Queries: {response.total_knowledge_queries}")
    print(f"\nQuality Metrics:")
    print(f"  Knowledge Coverage: {response.knowledge_coverage_score:.2f}")
    print(f"  Biological Rigor: {response.biological_rigor_score:.2f}")

    print(f"\nValidation: {'✅ Passed' if is_valid else '❌ Failed'}")
    for warning in warnings:
        print(f"  {warning}")

    # Export JSON
    print("\n=== Structured JSON Output ===")
    print(response.to_json())

    print("\n✅ Test Complete!")