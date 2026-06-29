from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.future import select
from app.agents.graph import graph
from app.models.models import Conversation, Message, AuditLog
from app.repositories.repositories import ConversationRepository, AuditLogRepository
from app.core.logging import logger

class LangGraphAgentsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.audit_repo = AuditLogRepository(db)

    async def run_workflow(self, user_id: UUID, ds_id: UUID, user_query: str, conversation_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Orchestrates running user request through LangGraph, creating a conversation session, 
        storing messages with structured agent step results.
        Enforces AI Daily Quota limits (AI-005) and trims conversation context length (AI-004).
        """
        logger.info(f"Starting LangGraph workflow for user {user_id} on datasource {ds_id}...")
        
        # 1. Enforce User AI Daily Quota limits (AI-005)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        
        # Count user queries in the last 24 hours
        quota_check = await self.db.execute(
            select(func.count(Message.id))
            .join(Conversation)
            .where(Conversation.user_id == user_id, Message.sender == "user", Message.created_at >= yesterday)
        )
        daily_usage_count = quota_check.scalar() or 0
        max_daily_quota = 100
        
        if daily_usage_count >= max_daily_quota:
            audit = AuditLog(
                user_id=user_id,
                action="AI_QUOTA_EXCEEDED",
                details=f"Blocked query due to daily limit: {daily_usage_count}/{max_daily_quota}."
            )
            await self.audit_repo.log(audit)
            await self.db.commit()
            raise ValueError(f"Daily AI Query quota reached ({daily_usage_count}/{max_daily_quota}). Please try again tomorrow or upgrade your plan.")
            
        # 2. Resolve or create Conversation
        if not conversation_id:
            conv = Conversation(
                user_id=user_id,
                title=user_query[:50] + ("..." if len(user_query) > 50 else "")
            )
            conv = await self.conv_repo.create(conv)
            conversation_id = conv.id
            logger.info(f"Created new conversation: {conversation_id}")
            
            # Log audit (ARCH-002)
            await self.audit_repo.log(AuditLog(
                user_id=user_id,
                action="CONVERSATION_CREATE",
                details=f"Created conversation: {conv.title}"
            ))
        else:
            conv = await self.conv_repo.get_by_id(conversation_id, user_id)
            if not conv:
                raise ValueError("Conversation not found or access denied.")
                
        # 3. Log user message
        user_msg = Message(
            conversation_id=conversation_id,
            sender="user",
            content=user_query
        )
        await self.conv_repo.add_message(user_msg)
        await self.db.flush()
        
        # 4. Token Budgeting & Context Trimming (AI-004)
        # Fetch existing messages directly via async query to avoid lazy load IO error
        res_msgs = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        all_msgs = list(res_msgs.scalars().all())
        trimmed_msgs = all_msgs[-10:] if len(all_msgs) > 10 else all_msgs
        
        conversation_history = [
            {"role": "user" if m.sender == "user" else "assistant", "content": m.content}
            for m in trimmed_msgs
        ]
        
        # 5. Construct initial LangGraph State
        initial_state = {
            "user_query": user_query,
            "data_source_id": str(ds_id),
            "next_agent": "supervisor",
            "classification": "",
            "schema_context": {},
            "query_plan": {},
            "generated_sql": "",
            "sql_explanation": "",
            "sql_optimization": {},
            "sql_errors": [],
            "debug_attempts": 0,
            "confidence_score": 0.0,
            "impact_analysis": {},
            "validation_result": {},
            "messages": [],
            "conversation_history": conversation_history  # Pass trimmed context history
        }
        
        # 6. Invoke LangGraph asynchronously
        import time
        start_time = time.perf_counter()
        try:
            final_state = await graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"LangGraph execution crashed: {e}")
            raise ValueError(f"LangGraph Orchestration Error: {str(e)}")
        finally:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"LangGraph workflow execution completed in {duration_ms}ms")
            
        # 7. Extract results
        classification = final_state.get("classification", "sql_gen")
        generated_sql = final_state.get("generated_sql", "")
        sql_explanation = final_state.get("sql_explanation", "")
        query_plan = final_state.get("query_plan", {})
        confidence_score = final_state.get("confidence_score", 0.0)
        impact_analysis = final_state.get("impact_analysis", {})
        validation = final_state.get("validation_result", {})
        optimization = final_state.get("sql_optimization", {})
        
        # 8. Save Assistant response with step details
        step_details = {
            "classification": classification,
            "query_plan": query_plan,
            "generated_sql": generated_sql,
            "confidence_score": confidence_score,
            "impact_analysis": impact_analysis,
            "validation": validation,
            "optimization": optimization,
            "internal_logs": final_state.get("messages", [])
        }
        
        content = sql_explanation or optimization.get("performance_analysis", "") or f"Action complete: {classification}"
        
        assistant_msg = Message(
            conversation_id=conversation_id,
            sender="assistant",
            content=content,
            step_details=step_details
        )
        saved_msg = await self.conv_repo.add_message(assistant_msg)
        
        # Log successful query/AI action audit (ARCH-002)
        await self.audit_repo.log(AuditLog(
            user_id=user_id,
            action="AI_WORKFLOW_SUCCESS",
            details=f"Completed {classification} workflow on datasource {ds_id} (conversation {conversation_id})."
        ))
        
        await self.db.commit()
        
        return {
            "conversation_id": conversation_id,
            "message_id": saved_msg.id,
            "classification": classification,
            "query_plan": query_plan,
            "generated_sql": generated_sql,
            "confidence_score": confidence_score,
            "impact_analysis": impact_analysis,
            "validation": validation,
            "optimization": optimization,
            "explanation": content
        }
