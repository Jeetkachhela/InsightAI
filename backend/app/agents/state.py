from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # Inputs
    user_query: str
    data_source_id: str
    
    # Workflow routing state
    next_agent: str          # e.g., "supervisor", "schema", "planner", "sql", "explain", "optimize", "debug", "end"
    classification: str      # "sql_gen", "sql_explain", "sql_optimize", "sql_debug"
    
    # Rich schema details extracted via RAG / schema discovery
    schema_context: Dict[str, Any]
    
    # Generated plan
    query_plan: Dict[str, Any]
    
    # SQL output
    generated_sql: str
    
    # Explanation text
    sql_explanation: str
    
    # Optimization recommendations
    sql_optimization: Dict[str, Any]
    
    # Debug/error trace states
    sql_errors: List[str]
    debug_attempts: int
    
    # Reliability metrics
    confidence_score: float
    impact_analysis: Dict[str, Any]
    validation_result: Dict[str, Any]
    
    # Message log (internal tracing & agent outputs)
    messages: List[Dict[str, Any]]
    
    # Conversational history for context budgeting (AI-004)
    conversation_history: List[Dict[str, str]]
