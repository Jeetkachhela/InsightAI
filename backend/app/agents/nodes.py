import json
import re
from typing import Dict, Any
from langchain_groq import ChatGroq
from app.core.config import settings
from app.core.security import is_safe_select_query
from app.agents.state import AgentState
from app.core.logging import logger

def get_llm():
    """
    Initializes the Groq LLM client.
    """
    try:
        return ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0.0,
            timeout=15.0,
            max_retries=0
        )
    except Exception as e:
        logger.error(f"Failed to initialize ChatGroq: {e}. AI features will run in mock/fallback mode.")
        return None

# Helper to clean JSON response from LLM
def parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Remove markdown code block wrappers if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n", "", text)
        text = re.sub(r"\n```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Regex fallback to find JSON block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"LLM output was not valid JSON: {text}")

# 1. Supervisor Agent
async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Supervisor Agent: Classifying user request...")
    user_query = state.get("user_query", "")
    
    llm = get_llm()
    if not llm:
        # Mock/fallback classifier for local tests
        classification = "sql_gen"
        if "explain" in user_query.lower() or "select" in user_query.lower():
            classification = "sql_explain"
        if "optimize" in user_query.lower() or "slow" in user_query.lower():
            classification = "sql_optimize"
        if "fix" in user_query.lower() or "error" in user_query.lower():
            classification = "sql_debug"
        
        logger.warning(f"Using mock classification: {classification}")
        return {
            "classification": classification,
            "next_agent": "schema" if classification == "sql_gen" else (
                "explain" if classification == "sql_explain" else (
                    "optimize" if classification == "sql_optimize" else "debug"
                )
            )
        }

    prompt = f"""You are the Supervisor Agent of InsightForge AI, a Schema-Aware SQL Intelligence Platform.
Classify the user's intent based on their query.

Available Classifications:
1. "sql_gen": The user is asking a natural language question and wants to retrieve data or generate a SELECT query (e.g. "find total sales for May").
2. "sql_explain": The user is asking to explain an existing SQL query, joins, or database concepts (e.g. "explain this query: SELECT...").
3. "sql_optimize": The user wants to optimize a SQL query or analyze its performance (e.g. "how do I optimize SELECT...").
4. "sql_debug": The user has a broken SQL query or an execution error they want to fix (e.g. "fix this error in SELECT...").

User Input: "{user_query}"

Respond ONLY with a valid JSON block inside a code fence, matching this schema:
{{
  "classification": "sql_gen" | "sql_explain" | "sql_optimize" | "sql_debug",
  "reason": "brief reason for classification"
}}
"""
    try:
        response = await llm.ainvoke(prompt)
        res_data = parse_json_response(response.content)
        classification = res_data["classification"]
    except Exception as e:
        logger.error(f"Supervisor LLM call failed: {e}. Defaulting to sql_gen.")
        classification = "sql_gen"

    # Route next agent
    if classification == "sql_gen":
        next_agent = "schema"
    elif classification == "sql_explain":
        next_agent = "explain"
    elif classification == "sql_optimize":
        next_agent = "optimize"
    else:
        next_agent = "debug"

    return {
        "classification": classification,
        "next_agent": next_agent,
        "messages": [{"role": "supervisor", "content": f"Classified query as '{classification}' (routing to '{next_agent}')"}]
    }

# 2. Schema Agent
# Note: The schema node is purely code-driven, querying our pgvector RAG database 
# to pull only top-k relevant tables/columns based on semantic matching.
async def schema_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Schema Agent: Retrieving relevant schema context...")
    ds_id = state.get("data_source_id")
    user_query = state.get("user_query")
    
    # We retrieve the RAG service dynamically to fetch context
    from app.services.rag import RAGService
    from app.core.database import AsyncSessionLocal
    
    rag_service = RAGService()
    async with AsyncSessionLocal() as db:
        try:
            # Get semantic context (tables + columns + relationships)
            context = await rag_service.retrieve_context(db, ds_id, user_query, top_k=6)
        except Exception as e:
            logger.error(f"Schema retrieval failed: {e}")
            context = {"tables": {}, "relationships": []}
            
    return {
        "schema_context": context,
        "next_agent": "sql",
        "messages": [{"role": "schema_agent", "content": f"Retrieved schema context containing tables: {list(context.get('tables', {}).keys())}"}]
    }

# 3. Planner Agent
async def planner_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Planner Agent: Structuring query execution plan...")
    user_query = state.get("user_query")
    schema_context = state.get("schema_context", {})
    
    if not schema_context.get("tables"):
        return {
            "query_plan": {},
            "next_agent": "sql",
            "messages": [{"role": "planner", "content": "No schema context available. Proceeding with empty plan."}]
        }
        
    llm = get_llm()
    if not llm:
        # Fallback query plan
        plan = {
            "tables": list(schema_context["tables"].keys())[:2],
            "joins": [],
            "filters": [],
            "aggregations": [],
            "metrics": []
        }
        return {
            "query_plan": plan,
            "next_agent": "sql",
            "messages": [{"role": "planner", "content": "Using fallback query plan."}]
        }
        
    prompt = f"""You are the Planner Agent of InsightForge AI.
Analyze the user request and draft a detailed SQL query plan.
Using ONLY the provided schema context, identify:
1. Target tables
2. Joins (if multiple tables are needed, list joining keys)
3. Filters (where conditions)
4. Aggregations (group by columns)
5. Metrics (sums, averages, counts)

Schema Context: {json.dumps(schema_context)}
User Query: "{user_query}"

Rules:
- NEVER assume or hallucinate tables or columns not present in the Schema Context.
- Prefer explicit columns in the schema.

Respond ONLY with a valid JSON block matching this schema:
{{
  "tables": ["table1", "table2"],
  "joins": [
    {{"source_table": "table1", "source_column": "id", "target_table": "table2", "target_column": "table1_id"}}
  ],
  "filters": ["table1.status = 'active'"],
  "aggregations": ["table2.category"],
  "metrics": ["SUM(table2.amount)"]
}}
"""
    try:
        response = await llm.ainvoke(prompt)
        plan = parse_json_response(response.content)
    except Exception as e:
        logger.error(f"Planner LLM call failed: {e}")
        plan = {"error": str(e)}

    return {
        "query_plan": plan,
        "next_agent": "sql",
        "messages": [{"role": "planner", "content": f"Created plan involving tables: {plan.get('tables', [])}"}]
    }

# 4. SQL Agent
async def sql_node(state: AgentState) -> Dict[str, Any]:
    logger.info("SQL Agent: Generating schema-aware SQL...")
    user_query = state.get("user_query")
    schema_context = state.get("schema_context", {})
    query_plan = state.get("query_plan", {})
    
    if not schema_context.get("tables"):
        error_msg = "Insufficient schema context available. Additional information or schema retrieval is required."
        return {
            "generated_sql": "",
            "sql_explanation": error_msg,
            "confidence_score": 0.0,
            "impact_analysis": {"error": "Missing schema"},
            "validation_result": {"is_safe": False, "error": error_msg},
            "next_agent": "end",
            "messages": [{"role": "sql_agent", "content": error_msg}]
        }
        
    llm = get_llm()
    if not llm:
        # Mock SQL generation fallback
        table = list(schema_context["tables"].keys())[0]
        col = schema_context["tables"][table][0]["column_name"]
        mock_sql = f"SELECT {col} FROM {table} LIMIT 10;"
        return {
            "generated_sql": mock_sql,
            "sql_explanation": f"Generated query to fetch records from table `{table}` based on the retrieved schema.",
            "confidence_score": 0.5,
            "impact_analysis": {"tables_scanned": [table], "join_count": 0, "aggregation_complexity": "low"},
            "validation_result": {"is_safe": True, "reason": "Query is safe."},
            "next_agent": "end",
            "messages": [{"role": "sql_agent", "content": f"Generated SQL: {mock_sql}"}]
        }

    prompt = f"""You are the SQL Agent of InsightForge AI.
Generate a PostgreSQL SELECT query and clear Markdown explanation to answer the user query based on the schema context.

Schema Context: {json.dumps(schema_context)}
User Query: "{user_query}"

Mandatory Rules:
1. ONLY return SELECT queries. Do NOT write INSERT, UPDATE, DELETE, or DDL queries.
2. Only reference tables and columns defined in the Schema Context. Never invent/hallucinate.
3. If the schema is insufficient to answer the query, output: "Insufficient schema context available. Additional information or schema retrieval is required."
4. Compute:
   - "confidence_score": Float (0.0 to 1.0) assessing how closely the schema columns map to the user request.
   - "impact_analysis": JSON evaluating rows scanned, join counts, and query complexity.

Respond ONLY with a valid JSON block:
{{
  "sql": "SELECT ...",
  "explanation": "Clear Markdown explanation of what the SQL query does and the columns referenced.",
  "confidence_score": 0.95,
  "impact_analysis": {{
    "tables_scanned": ["table1"],
    "join_count": 0,
    "aggregation_complexity": "low" | "medium" | "high"
  }}
}}
"""
    try:
        response = await llm.ainvoke(prompt)
        res_data = parse_json_response(response.content)
        sql = res_data.get("sql", "").strip()
        explanation = res_data.get("explanation", "Query generated successfully based on database schema.")
        confidence = res_data.get("confidence_score", 0.0)
        impact = res_data.get("impact_analysis", {})
    except Exception as e:
        logger.error(f"SQL Agent LLM call failed: {e}")
        sql = "SELECT 'error' as status;"
        explanation = f"Failed to generate SQL query: {str(e)}"
        confidence = 0.0
        impact = {"error": str(e)}

    # SQL Firewall Validation Check
    is_safe, firewall_reason = is_safe_select_query(sql)
    validation = {
        "is_safe": is_safe,
        "reason": firewall_reason
    }

    return {
        "generated_sql": sql,
        "sql_explanation": explanation,
        "confidence_score": confidence,
        "impact_analysis": impact,
        "validation_result": validation,
        "next_agent": "end",
        "messages": [{"role": "sql_agent", "content": f"Generated query with confidence {confidence}"}]
    }

# 5. Explain Agent
async def explain_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Explain Agent: Formulating query explanation...")
    sql = state.get("generated_sql") or state.get("user_query")
    schema_context = state.get("schema_context", {})
    
    llm = get_llm()
    if not llm:
        return {
            "sql_explanation": "This is a query to select records from the database. (Mock Explanation)",
            "next_agent": "end",
            "messages": [{"role": "explain_agent", "content": "Explanation compiled."}]
        }
        
    prompt = f"""You are the Explain Agent of InsightForge AI.
Explain this SQL query in plain, easy-to-understand language.
Break down what tables are queried, the JOIN conditions, filters, group bys, and what the overall calculation represents.
If the system is teaching the user, explain any fundamental SQL concepts used (e.g. how INNER JOIN vs LEFT JOIN works, or how GROUP BY groups records).

SQL Query:
{sql}

Schema Context:
{json.dumps(schema_context)}

Provide a clear and concise Markdown explanation.
"""
    try:
        response = await llm.ainvoke(prompt)
        explanation = response.content
    except Exception as e:
        logger.error(f"Explain Agent LLM call failed: {e}")
        explanation = f"Failed to generate explanation: {e}"

    return {
        "sql_explanation": explanation,
        "next_agent": "end",
        "messages": [{"role": "explain_agent", "content": "Explanation generated."}]
    }

# 6. Optimization Agent
async def optimize_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Optimization Agent: Analyzing query performance...")
    user_query = state.get("user_query", "")
    
    # Extract SQL from query
    sql_match = re.search(r"select\s+.*", user_query, re.IGNORECASE | re.DOTALL)
    sql = sql_match.group(0) if sql_match else user_query
    
    llm = get_llm()
    if not llm:
        return {
            "sql_optimization": {
                "original_sql": sql,
                "optimized_sql": sql,
                "performance_analysis": "No indexes detected. (Mock Analysis)",
                "recommendations": ["Create indexes on joining keys."]
            },
            "next_agent": "end",
            "messages": [{"role": "optimization_agent", "content": "Optimization recommendations prepared."}]
        }
        
    prompt = f"""You are the Optimization Agent of InsightForge AI.
Analyze this SQL query for performance improvements.
Suggest indexing, rewrites (e.g. replacing subqueries with joins or CTEs), or structural changes.

SQL Query:
{sql}

Respond ONLY with a valid JSON block:
{{
  "optimized_sql": "SELECT ...",
  "performance_analysis": "Explanation of potential performance bottlenecks in original SQL",
  "recommendations": [
    "Create an index on table1(col1)",
    "Use a JOIN instead of subquery"
  ]
}}
"""
    try:
        response = await llm.ainvoke(prompt)
        opt_data = parse_json_response(response.content)
    except Exception as e:
        logger.error(f"Optimization Agent LLM call failed: {e}")
        opt_data = {"error": str(e)}

    return {
        "sql_optimization": opt_data,
        "next_agent": "end",
        "messages": [{"role": "optimization_agent", "content": "Optimizations completed."}]
    }

# 7. Debug Agent
async def debug_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Debug Agent: Analyzing SQL error...")
    user_query = state.get("user_query", "")
    
    # In debug mode, the user query contains a broken SQL query and an error message.
    # We can separate them or let the model do it.
    
    llm = get_llm()
    if not llm:
        return {
            "generated_sql": user_query,
            "sql_explanation": "Could not verify syntax error. (Mock Debugger)",
            "next_agent": "end",
            "messages": [{"role": "debug_agent", "content": "Debug fallback executed."}]
        }
        
    prompt = f"""You are the Debug Agent of InsightForge AI.
The user has reported an issue or error with a SQL query.
Fix the syntax or logical errors in their query and explain what went wrong.

User Request/Error:
"{user_query}"

Respond ONLY with a valid JSON block:
{{
  "corrected_sql": "SELECT ...",
  "error_detected": "Syntax error at or near...",
  "explanation": "Markdown description of why the error occurred and how it was fixed."
}}
"""
    try:
        response = await llm.ainvoke(prompt)
        debug_data = parse_json_response(response.content)
        corrected_sql = debug_data.get("corrected_sql", "")
        explanation = debug_data.get("explanation", "")
    except Exception as e:
        logger.error(f"Debug Agent LLM call failed: {e}")
        corrected_sql = "SELECT 'debug_error';"
        explanation = f"Debugger error: {e}"

    return {
        "generated_sql": corrected_sql,
        "sql_explanation": explanation,
        "next_agent": "end",
        "messages": [{"role": "debug_agent", "content": "SQL debugging complete."}]
    }
